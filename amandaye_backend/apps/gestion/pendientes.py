"""Permission-scoped, paginated queues. All operations in this module are reads."""
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import CharField, DecimalField, Exists, F, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.cobranzas.models import AplicacionPago, Cargo, IntencionSaldo, Pago
from apps.usuarios.models import Personas, Socios
from apps.usuarios.services.habilitacion import preparar_diagnosticos
from .forms import PendientesForm

PAGE_KEYS = ('solicitudes_page', 'saldos_page', 'deudas_page', 'habilitaciones_page')


def _page(request, queryset, key, anchor, fields):
    page = Paginator(queryset, 25).get_page(request.GET.get(key))
    params = request.GET.copy()
    for name in list(params):
        if name not in (*PAGE_KEYS, *fields):
            del params[name]
    for attr, number in (('anterior_url', page.previous_page_number() if page.has_previous() else None),
                         ('siguiente_url', page.next_page_number() if page.has_next() else None)):
        if number is not None:
            params[key] = number
            setattr(page, attr, '?' + params.urlencode() + '#' + anchor)
    return page


def _aplicado():
    return Coalesce(Sum('aplicaciones__importe_aplicado', filter=Q(aplicaciones__estado=AplicacionPago.Estado.ACTIVA)),
                    Value(Decimal('0.00')), output_field=DecimalField(max_digits=16, decimal_places=2))


def cargar_pendientes(request, context):
    form = PendientesForm(request.GET, **{k: context[k] for k in ('can_socios', 'can_cuentas', 'can_personas')})
    valid = form.is_valid()
    filtros = form.cleaned_data if valid else {}
    numero = filtros.get('socio')
    context.update(filtros=form, fecha_evaluacion=timezone.localdate())
    def filtered(qs, socio_field):
        if not valid:
            return qs.none()
        return qs.filter(**{socio_field: numero}) if numero is not None else qs
    if context['can_socios']:
        qs = filtered(Socios.objects.filter(activo=2), 'numero')
        for name, lookup in (('solicitudes_desde', 'fechaSolicitud__gte'), ('solicitudes_hasta', 'fechaSolicitud__lte')):
            if filtros.get(name):
                qs = qs.filter(**{lookup: filtros[name]})
        context['solicitudes'] = _page(request, qs.order_by('fechaSolicitud', 'numero'), 'solicitudes_page', 'solicitudes', form.fields)
    if context['can_cuentas']:
        pagos = filtered(Pago.objects.select_related('cuenta', 'intencion_saldo').annotate(
            saldo_sin_aplicar=F('importe_total') - _aplicado(),
            intencion_actual=Coalesce('intencion_saldo__intencion', Value(IntencionSaldo.SIN_CLASIFICAR), output_field=CharField()),
        ).filter(saldo_sin_aplicar__gt=0), 'cuenta__socio_titular_id')
        if filtros.get('intencion'):
            pagos = pagos.filter(intencion_actual=filtros['intencion'])
        context['pagos_sin_aplicar'] = _page(request, pagos.order_by('fecha_pago', 'pk'), 'saldos_page', 'saldos', form.fields)
        for pago in context['pagos_sin_aplicar']:
            pago.intencion_label = dict(IntencionSaldo.choices)[pago.intencion_actual]
        cargos = filtered(Cargo.objects.select_related('cuenta', 'concepto').annotate(
            saldo_pendiente_panel=F('importe') - _aplicado()).filter(
            estado__in=(Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL),
            fecha_vencimiento__lt=timezone.localdate(), saldo_pendiente_panel__gt=0), 'cuenta__socio_titular_id')
        if filtros.get('vencimiento_hasta'):
            cargos = cargos.filter(fecha_vencimiento__lte=filtros['vencimiento_hasta'])
        context['deudas_vencidas'] = _page(request, cargos.order_by('fecha_vencimiento', 'pk'), 'deudas_page', 'deudas', form.fields)
    if context['can_personas']:
        personas = filtered(Personas.objects.annotate(socio_existe=Exists(Socios.objects.filter(numero=OuterRef('numeroSocio')))), 'numeroSocio')
        estado = filtros.get('habilitacion')
        if not estado:
            personas = personas.filter(estado_habilitacion__in=('NO_HABILITADO', 'SUSPENDIDO'))
        elif estado != 'TODOS':
            personas = personas.filter(estado_habilitacion=estado)
        page = _page(request, personas.order_by('estado_habilitacion', 'numeroSocio', 'Cedula'), 'habilitaciones_page', 'habilitaciones', form.fields)
        if context['can_socios'] and context['can_cuentas']:
            preparar_diagnosticos(page)
        context['habilitaciones'] = page
    return context
