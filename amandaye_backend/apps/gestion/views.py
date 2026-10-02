import html
import json
from decimal import Decimal
from uuid import uuid4

from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages

from apps.cobranzas.models import AplicacionPago, Cargo, ComprobantePago, CuentaCorriente, Pago
from apps.cobranzas.services.cobros import confirmar_cobro, proponer_aplicaciones
from apps.cobranzas.services.comprobantes import generar_pdf, obtener_comprobante
from apps.cobranzas.services.cuentas import obtener_estado_cuenta
from apps.usuarios.models import Embarcaciones, Personas, Socios

from .forms import CobroForm


def _puede(request, permiso):
    return request.user.is_active and request.user.is_staff and request.user.has_perm(permiso)


def _puede_dashboard(request):
    return any(_puede(request, permiso) for permiso in (
        'usuarios.view_socios',
        'usuarios.view_personas',
        'cobranzas.view_cuentacorriente',
    ))


def _saldo_pago_expression():
    aplicadas = Coalesce(
        Sum(
            'aplicaciones__importe_aplicado',
            filter=Q(aplicaciones__estado=AplicacionPago.Estado.ACTIVA),
        ),
        Value(Decimal('0.00')),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    return F('importe_total') - aplicadas


@login_required
def dashboard(request):
    if not _puede_dashboard(request):
        raise PermissionDenied

    context = {
        'title': 'Gestión diaria',
        'can_socios': _puede(request, 'usuarios.view_socios'),
        'can_personas': _puede(request, 'usuarios.view_personas'),
        'can_cuentas': _puede(request, 'cobranzas.view_cuentacorriente'),
        'can_resumen': _puede(request, 'cobranzas.puede_ver_resumen_cobranzas'),
        'pendientes': [],
    }
    if context['can_socios']:
        context['solicitudes'] = Socios.objects.filter(activo=2).order_by('fechaSolicitud', 'numero')[:10]
    if context['can_cuentas']:
        context['pagos_sin_aplicar'] = (
            Pago.objects.select_related('cuenta__socio_titular')
            .annotate(saldo_sin_aplicar=_saldo_pago_expression())
            .filter(saldo_sin_aplicar__gt=0)
            .order_by('fecha_pago', 'pk')[:10]
        )
        context['deudas_vencidas'] = (
            Cargo.objects.select_related('cuenta__socio_titular', 'concepto')
            .filter(
                estado__in=(Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL),
                fecha_vencimiento__lt=timezone.localdate(),
            )
            .order_by('fecha_vencimiento', 'pk')[:10]
        )
    if context['can_personas']:
        context['habilitaciones'] = (
            Personas.objects.filter(estado_habilitacion__in=('NO_HABILITADO', 'SUSPENDIDO'))
            .order_by('estado_habilitacion', 'numeroSocio', 'Cedula')[:10]
        )
    return render(request, 'gestion/dashboard.html', context)


@login_required
def buscar_socios(request):
    if not _puede(request, 'usuarios.view_socios'):
        raise PermissionDenied
    query = request.GET.get('q', '').strip()
    socios = Socios.objects.none()
    if query:
        names = Personas.objects.filter(
            Q(Cedula__icontains=query)
            | Q(PrimerNombre__icontains=query)
            | Q(SegundoNombre__icontains=query)
            | Q(PrimerApellido__icontains=query)
            | Q(SegundoApellido__icontains=query)
        ).values('Cedula')
        criteria = Q(cedulaTitular__in=names) | Q(cedulaTitular__icontains=query)
        if query.isdigit():
            criteria |= Q(numero=int(query))
        socios = Socios.objects.filter(criteria).order_by('numero').distinct()
    paginator = Paginator(socios, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'gestion/buscar_socios.html', {
        'title': 'Buscar socio', 'query': query, 'page': page,
    })


@login_required
def ficha_socio(request, numero):
    can_socios = _puede(request, 'usuarios.view_socios')
    can_personas = _puede(request, 'usuarios.view_personas')
    can_cuentas = _puede(request, 'cobranzas.view_cuentacorriente')
    if not (can_socios or can_personas or can_cuentas):
        raise PermissionDenied

    socio = get_object_or_404(Socios, pk=numero) if can_socios else None
    persona = None
    familiares = Personas.objects.none()
    if can_personas and socio:
        persona = Personas.objects.filter(Cedula=socio.cedulaTitular).first()
        familiares = Personas.objects.filter(numeroSocio=socio.numero).order_by('relacionTitular', 'Cedula')
    cuenta = None
    estado = None
    if can_cuentas and socio:
        cuenta = CuentaCorriente.objects.filter(socio_titular=socio).first()
        if cuenta:
            estado = obtener_estado_cuenta(cuenta)
            estado['cargos'] = list(estado['cargos'][:25])
            estado['pagos'] = list(estado['pagos'][:25])
            recibos = dict(ComprobantePago.objects.filter(
                pago_id__in=[pago.pk for pago in estado['pagos']],
            ).values_list('pago_id', 'numero'))
            for pago in estado['pagos']:
                pago.comprobante_numero = recibos.get(pago.pk)
    embarcaciones = Embarcaciones.objects.filter(id_socio=numero).order_by('numero') if can_personas else []
    historial = []
    if can_socios:
        socio_type = ContentType.objects.get_for_model(Socios)
        historial = LogEntry.objects.filter(
            content_type=socio_type, object_id=str(numero),
        ).select_related('user').order_by('-action_time')[:25]
    return render(request, 'gestion/ficha_socio.html', {
        'title': f'Ficha del socio {numero}', 'socio': socio, 'persona': persona,
        'familiares': familiares, 'cuenta': cuenta, 'estado': estado,
        'embarcaciones': embarcaciones, 'historial': historial,
        'can_personas': can_personas, 'can_cuentas': can_cuentas,
        'can_cobrar': can_cuentas and _puede(request, 'cobranzas.add_pago') and
        _puede(request, 'cobranzas.puede_aplicar_pago'),
    })


@login_required
def nuevo_cobro(request, numero):
    if not (_puede(request, 'usuarios.view_socios') and
            _puede(request, 'cobranzas.view_cuentacorriente') and
            _puede(request, 'cobranzas.add_pago') and
            _puede(request, 'cobranzas.puede_aplicar_pago')):
        raise PermissionDenied
    socio = get_object_or_404(Socios, pk=numero)
    cuenta = get_object_or_404(CuentaCorriente, socio_titular=socio)
    form = CobroForm(request.POST or None)
    propuesta = None
    aplicaciones_json = ''
    clave = request.POST.get('clave') or str(uuid4())
    if request.method == 'POST' and form.is_valid():
        if request.POST.get('confirmar'):
            try:
                aplicaciones = json.loads(html.unescape(request.POST.get('aplicaciones', '[]')))
                operation = confirmar_cobro(
                    cuenta=cuenta, usuario=request.user, clave=clave,
                    fecha_pago=form.cleaned_data['fecha_pago'],
                    importe_total=form.cleaned_data['importe_total'],
                    medio_pago=form.cleaned_data['medio_pago'],
                    referencia=form.cleaned_data.get('referencia', ''),
                    aplicaciones=aplicaciones,
                    intencion_saldo=form.cleaned_data['intencion_saldo'],
                    version=request.POST.get('version') or None,
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                form.add_error(None, f'La propuesta no se pudo leer: {exc}')
            except ValidationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f'Cobro registrado. Comprobante {operation.pago_id}.')
                return redirect('gestion:comprobante_pago', pago_id=operation.pago_id)
        else:
            try:
                propuesta = proponer_aplicaciones(
                    cuenta, form.cleaned_data['importe_total'], usuario=request.user,
                )
                aplicaciones_json = json.dumps(propuesta['filas'], ensure_ascii=True)
            except Exception as exc:
                form.add_error(None, str(exc))
    return render(request, 'gestion/cobro.html', {
        'title': f'Registrar cobro · Socio {numero}', 'socio': socio,
        'cuenta': cuenta, 'form': form, 'propuesta': propuesta,
        'aplicaciones_json': aplicaciones_json, 'clave': clave,
    })


@login_required
def comprobante_pago(request, pago_id):
    if not _puede(request, 'cobranzas.view_pago'):
        raise PermissionDenied
    pago = get_object_or_404(Pago.objects.select_related('cuenta__socio_titular'), pk=pago_id)
    try:
        comprobante = obtener_comprobante(pago, usuario=request.user)
    except ComprobantePago.DoesNotExist:
        messages.error(request, 'Este pago todavía no tiene comprobante interno.')
        return redirect('gestion:ficha_socio', numero=pago.cuenta.socio_titular_id)
    response = HttpResponse(generar_pdf(comprobante, usuario=request.user), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{comprobante.numero}.pdf"'
    return response
