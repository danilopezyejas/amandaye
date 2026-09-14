import datetime
import logging
import re
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.cobranzas.models import CuentaCorriente, ConceptoCobro, Cargo
from apps.usuarios.models import Socios, Historico_socios, Personas
from apps.cobranzas.services.cargos import crear_cargo

logger = logging.getLogger(__name__)


def generar_cuotas_mensuales(periodo: str):
    """Generate one monthly charge per active account, serialized with closure."""
    try:
        if not isinstance(periodo, str) or not re.fullmatch(r'\d{4}-\d{2}', periodo):
            raise ValueError
        year, month = map(int, periodo.split('-'))
        emision = datetime.date(year, month, 1)
        vencimiento = datetime.date(year, month, 10)
    except ValueError:
        return {'error': 'El periodo debe tener formato YYYY-MM.'}

    codigos = ('CUOTA_INDIVIDUAL', 'CUOTA_FAMILIAR', 'CUOTA_TEMPORADA', 'MATRICULA')
    conceptos = {c.codigo: c for c in ConceptoCobro.objects.filter(codigo__in=codigos)}
    if len(conceptos) != len(codigos):
        return {'error': 'Faltan configurar los conceptos de cobro base.'}
    for concepto in conceptos.values():
        if concepto.importe_por_defecto <= 0:
            return {'error': f'El importe de {concepto.codigo} debe ser mayor a 0.'}

    cuentas = list(CuentaCorriente.objects.filter(
        estado=CuentaCorriente.Estado.ACTIVA, socio_titular__activo=1,
    ).values_list('pk', 'socio_titular_id'))
    resultados = {'cuentas_procesadas': 0, 'cuotas_creadas': 0, 'cuotas_omitidas': 0, 'errores': []}

    activos = Socios.objects.filter(activo=1)
    Historico_socios.objects.get_or_create(fecha=emision, defaults={
        'familiar': activos.filter(tipo_socio='FAMILIAR').count(),
        'individual': activos.filter(tipo_socio='INDIVIDUAL').count(),
        'total': activos.count(),
        'personas': Personas.objects.filter(numeroSocio__in=activos.values('numero')).count(),
    })

    for cuenta_id, socio_id in cuentas:
        resultados['cuentas_procesadas'] += 1
        try:
            creadas = _generar_cuota_cuenta(cuenta_id, socio_id, conceptos, periodo, emision, vencimiento)
            resultados['cuotas_creadas'] += creadas
            if not creadas:
                resultados['cuotas_omitidas'] += 1
        except ValidationError as exc:
            resultados['errores'].append(f'Socio {socio_id}: ' + '; '.join(exc.messages))
        except Exception as exc:
            logger.error('Error al generar cuota para cuenta %s (%s)', cuenta_id, type(exc).__name__)
            resultados['errores'].append(f'No se pudo generar la cuota del socio {socio_id}.')
    return resultados


@transaction.atomic
def _generar_cuota_cuenta(cuenta_id, socio_id, conceptos, periodo, emision, vencimiento):
    # Socio precedes Cuenta for transitions/generation. Financial payment
    # writers never lock Socio, so they keep Cuenta -> Pago -> Cargo order.
    socio = Socios.objects.select_for_update().get(pk=socio_id)
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta_id)
    if socio.activo != 1 or cuenta.estado != CuentaCorriente.Estado.ACTIVA or socio.tipo_cuota == 'EXONERADO':
        return 0
    codigo = ('CUOTA_TEMPORADA' if socio.tipo_cuota == 'TEMPORADA' else
              'CUOTA_FAMILIAR' if socio.tipo_socio == 'FAMILIAR' else 'CUOTA_INDIVIDUAL')
    concepto = conceptos[codigo]
    # Current reads also prevent duplicate generation under REPEATABLE READ.
    if list(Cargo.objects.select_for_update().filter(cuenta=cuenta, concepto=concepto, periodo=periodo)):
        return 0
    importe = concepto.importe_por_defecto
    if socio.tipo_cuota == 'BECA':
        importe = round(importe * Decimal('0.50'), 2)
    crear_cargo(cuenta, concepto, periodo, emision, vencimiento, importe)
    creadas = 1
    if (socio.fechaAprobacion and socio.fechaBaja
            and (socio.fechaAprobacion.year, socio.fechaAprobacion.month) == (emision.year, emision.month)
            and (socio.fechaAprobacion - socio.fechaBaja).days <= 365):
        matricula = conceptos['MATRICULA']
        if not list(Cargo.objects.select_for_update().filter(cuenta=cuenta, concepto=matricula, periodo=periodo)):
            crear_cargo(cuenta, matricula, periodo, emision, vencimiento,
                        matricula.importe_por_defecto * Decimal('2.00'), 'Matrícula doble por reafiliación temprana')
            creadas += 1
    from apps.usuarios.services.habilitacion import recalcular_habilitados
    recalcular_habilitados(socio_id=socio.pk)
    return creadas
