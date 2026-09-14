import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.cobranzas.models import AplicacionPago, Cargo, ConceptoCobro, CuentaCorriente
from apps.cobranzas.services.movimientos import exigir_permiso, validar_importe


@transaction.atomic
def crear_cargo(cuenta: CuentaCorriente, concepto: ConceptoCobro, periodo: str,
                fecha_emision: datetime.date, fecha_vencimiento: datetime.date,
                importe: Decimal, observaciones=None, usuario=None) -> Cargo:
    # Internal approval/generation also use this service; manual entry points
    # enforce add_cargo before calling it.
    importe = validar_importe(importe)
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta.pk)
    if cuenta.estado != CuentaCorriente.Estado.ACTIVA:
        raise ValidationError('No se pueden generar cargos en una cuenta cerrada.')
    cargo = Cargo(cuenta=cuenta, concepto=concepto, periodo=periodo,
                  fecha_emision=fecha_emision, fecha_vencimiento=fecha_vencimiento,
                  importe=importe, estado=Cargo.Estado.PENDIENTE,
                  observaciones=observaciones, registrado_por=usuario)
    cargo.full_clean()
    cargo.save()
    return cargo


@transaction.atomic
def anular_cargo(cargo: Cargo, observaciones=None, usuario=None) -> Cargo:
    exigir_permiso(usuario, 'cobranzas.puede_anular_cargo')
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cargo.cuenta_id)
    cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
    if cargo.cuenta_id != cuenta.pk:
        raise ValidationError('El cargo cambió de cuenta; vuelva a cargarlo.')
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError('El cargo ya se encuentra anulado.')
    activas = list(AplicacionPago.objects.select_for_update().filter(
        cargo_id=cargo.pk, estado=AplicacionPago.Estado.ACTIVA,
    ).order_by('pk'))
    if activas:
        raise ValidationError('Revierta las aplicaciones activas antes de anular el cargo.')
    cargo.estado = Cargo.Estado.ANULADO
    cargo.anulado_por = usuario
    cargo.fecha_anulacion = timezone.now()
    if observaciones:
        cargo.observaciones = (cargo.observaciones or '') + '\nANULADO: ' + observaciones
    cargo.save(update_fields=['estado', 'observaciones', 'anulado_por', 'fecha_anulacion', 'updated_at'])
    from apps.usuarios.services.habilitacion import recalcular_habilitados
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)
    return cargo
