"""Lecturas acotadas para la ficha; no escriben ni compensan saldos."""
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Case, CharField, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from apps.cobranzas.models import AplicacionPago, Cargo, Pago, ComprobantePago, OperacionCobro
from apps.usuarios.models import EventoSocio, Socios


def paginar(request, queryset, parametro, ancla):
    page = Paginator(queryset, 25).get_page(request.GET.get(parametro))
    # Only preserve known pagination inputs, not arbitrary URL data.
    params = request.GET.copy()
    for key in list(params):
        if key not in ('cargos_page', 'pagos_page', 'aplicaciones_page', 'historial_page'):
            del params[key]
    for attr, number in (('anterior_url', page.previous_page_number() if page.has_previous() else None),
                         ('siguiente_url', page.next_page_number() if page.has_next() else None)):
        if number is not None:
            params[parametro] = number
            setattr(page, attr, '?' + params.urlencode() + '#' + ancla)
    return page


def movimientos_cuenta(cuenta):
    money = DecimalField(max_digits=16, decimal_places=2)
    aplicado = Coalesce(Sum('aplicaciones__importe_aplicado',
                           filter=Q(aplicaciones__estado=AplicacionPago.Estado.ACTIVA)),
                         Value(Decimal('0.00')), output_field=money)
    cargos = cuenta.cargos.annotate(saldo_lectura=Case(
        When(estado=Cargo.Estado.ANULADO, then=Value(Decimal('0.00'))),
        default=F('importe') - aplicado, output_field=money,
    ))
    pagos = cuenta.pagos.annotate(saldo_lectura=F('importe_total') - aplicado)
    totales = cargos.aggregate(
        saldo_total=Coalesce(Sum('saldo_lectura'), Value(Decimal('0.00')), output_field=money),
        deuda_vencida=Coalesce(Sum('saldo_lectura', filter=Q(
            fecha_vencimiento__lt=timezone.localdate(), saldo_lectura__gt=0)),
            Value(Decimal('0.00')), output_field=money),
    )
    totales['saldo_sin_aplicar'] = pagos.aggregate(total=Coalesce(
        Sum('saldo_lectura'), Value(Decimal('0.00')), output_field=money))['total']
    totales['estado_cuenta'] = ('AL_DIA' if totales['saldo_total'] <= 0 else
                               'MOROSO' if cuenta.estado == 'CERRADA' else 'CON_DEUDA')
    return totales, cargos.select_related('concepto').order_by('-fecha_emision', '-pk'), pagos.order_by('-fecha_pago', '-pk')


def _eventos(queryset, fecha, actor, fuente, accion, recurso):
    # Equal projection types across SQL UNION branches (including MySQL).
    return queryset.order_by().annotate(
        h_fecha=F(fecha), h_actor=Cast(F(actor), CharField()),
        h_fuente=Value(fuente, output_field=CharField()),
        h_accion=accion, h_recurso=Cast(recurso, CharField()), h_id=F('pk'),
    ).values('h_fecha', 'h_actor', 'h_fuente', 'h_accion', 'h_recurso', 'h_id')


def historial_socio(socio, cuenta=None, *, comprobantes=False):
    sources = [
        _eventos(EventoSocio.objects.filter(socio=socio), 'fecha', 'actor__username',
                 'Socios', F('accion'), F('socio_id')),
        _eventos(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Socios), object_id=str(socio.pk)),
            'action_time', 'user__username', 'Administrador',
            Cast(F('action_flag'), CharField()), F('object_id')),
    ]
    if cuenta is not None:
        cargos = Cargo.objects.filter(cuenta=cuenta)
        pagos = Pago.objects.filter(cuenta=cuenta)
        aplicaciones = AplicacionPago.objects.filter(pago__cuenta=cuenta, cargo__cuenta=cuenta)
        for queryset, fecha, actor, accion, recurso in (
            (cargos, 'created_at', 'registrado_por__username', 'Cargo emitido', F('pk')),
            (cargos.filter(fecha_anulacion__isnull=False), 'fecha_anulacion', 'anulado_por__username', 'Cargo anulado', F('pk')),
            (pagos, 'created_at', 'registrado_por__username', 'Pago registrado', F('pk')),
            (aplicaciones, 'created_at', 'registrado_por__username', 'Pago aplicado', F('pk')),
            (aplicaciones.filter(fecha_reversion__isnull=False), 'fecha_reversion', 'revertido_por__username', 'Aplicación revertida', F('pk')),
            (OperacionCobro.objects.filter(cuenta=cuenta), 'creado_en', 'usuario__username', 'Operación de cobro confirmada', F('pk')),
            (ComprobantePago.objects.filter(pago__cuenta=cuenta) if comprobantes else ComprobantePago.objects.none(), 'emitido_en', 'emitido_por__username', 'Comprobante emitido', F('numero')),
        ):
            sources.append(_eventos(queryset, fecha, actor, 'Cobranzas', Value(accion, output_field=CharField()), recurso))
    # Sorting and LIMIT happen in SQL, not after loading every movement.
    return sources[0].union(*sources[1:], all=True).order_by('-h_fecha', 'h_fuente', '-h_id', 'h_accion')


def describir_historial(page):
    acciones = dict(EventoSocio.Accion.choices)
    for event in page:
        if event['h_fuente'] == 'Socios':
            event['h_accion'] = acciones.get(event['h_accion'], 'Transición de socio')
        elif event['h_fuente'] == 'Administrador':
            event['h_accion'] = {'1': 'Registro creado', '2': 'Datos actualizados', '3': 'Registro eliminado'}.get(event['h_accion'], 'Cambio administrativo')
        # Do not expose free-form admin messages, health data or legacy comments.
    return page
