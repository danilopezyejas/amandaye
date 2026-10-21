from decimal import Decimal
from uuid import uuid4

from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.cobranzas.models import AplicacionPago, Cargo, ComprobantePago, CuentaCorriente, Pago
from apps.cobranzas.services.cobros import aplicar_saldo, confirmar_cobro, proponer_aplicaciones
from apps.cobranzas.services.comprobantes import generar_pdf, obtener_comprobante
from apps.usuarios.models import Embarcaciones, Personas, Socios

from .forms import CobroForm, DistribucionForm, SaldoForm
from .consultas import paginar, movimientos_cuenta, historial_socio, describir_historial


def _puede(request, permiso):
    return request.user.is_active and request.user.is_staff and request.user.has_perm(permiso)


def _puede_aplicar(request):
    return all(_puede(request, permiso) for permiso in (
        'usuarios.view_socios', 'cobranzas.view_cuentacorriente',
        'cobranzas.view_pago', 'cobranzas.puede_aplicar_pago',
    ))


def _puede_dashboard(request):
    return any(_puede(request, permiso) for permiso in (
        'usuarios.view_socios',
        'usuarios.view_personas',
        'cobranzas.view_cuentacorriente',
    ))


@login_required
@never_cache
def dashboard(request):
    if not _puede_dashboard(request):
        raise PermissionDenied
    from .pendientes import cargar_pendientes
    context = {
        **admin.site.each_context(request), 'title': 'Gestión diaria',
        'can_socios': _puede(request, 'usuarios.view_socios'),
        'can_personas': _puede(request, 'usuarios.view_personas'),
        'can_cuentas': _puede(request, 'cobranzas.view_cuentacorriente'),
        'can_aplicar': _puede_aplicar(request),
        'can_cobrar': _puede_aplicar(request) and _puede(request, 'cobranzas.add_pago'),
    }
    return render(request, 'gestion/dashboard.html', cargar_pendientes(request, context))


@login_required
@never_cache
def buscar_socios(request):
    if not _puede(request, 'usuarios.view_socios'):
        raise PermissionDenied
    query = request.GET.get('q', '').strip()[:100]
    can_personas = _puede(request, 'usuarios.view_personas')
    socios = Socios.objects.none()
    # MySQL's collation can consider superscript/full-width digits equal to ASCII.
    query_error = ('Usá dígitos del 0 al 9 para buscar por número o cédula.'
                   if any(token.isdigit() and not token.isascii() for token in query.split()) else '')
    if query and not query_error:
        criteria = Q(cedulaTitular__icontains=query)
        if query.isascii() and query.isdigit() and len(query) <= 10 and int(query) <= 2147483647:
            criteria |= Q(numero=int(query))
        if can_personas:
            personas = Personas.objects.all()
            for token in query.split():
                personas = personas.filter(
                    Q(Cedula__icontains=token) | Q(PrimerNombre__icontains=token)
                    | Q(SegundoNombre__icontains=token) | Q(PrimerApellido__icontains=token)
                    | Q(SegundoApellido__icontains=token))
            criteria |= Q(numero__in=personas.values('numeroSocio'))
        socios = Socios.objects.filter(criteria).order_by('numero')
    page = Paginator(socios, 25).get_page(request.GET.get('page'))
    if can_personas:
        titulares = {p.Cedula: p for p in Personas.objects.filter(
            Cedula__in=[s.cedulaTitular for s in page])}
        for socio in page:
            titular = titulares.get(socio.cedulaTitular)
            if titular and titular.numeroSocio == socio.numero:
                socio.nombre_titular = ' '.join(titular.nombre_completo().split())
    return render(request, 'gestion/buscar_socios.html', {
        **admin.site.each_context(request), 'title': 'Buscar socio',
        'query': query, 'page': page, 'can_personas': can_personas, 'query_error': query_error,
    })


@login_required
@never_cache
def ficha_socio(request, numero):
    if not _puede(request, 'usuarios.view_socios'):
        raise PermissionDenied
    can_personas = _puede(request, 'usuarios.view_personas')
    can_cuentas = _puede(request, 'cobranzas.view_cuentacorriente')
    socio = get_object_or_404(Socios, pk=numero)
    persona = None
    familiares = []
    advertencias = []
    if can_personas:
        persona = Personas.objects.filter(Cedula=socio.cedulaTitular).first()
        if persona and persona.numeroSocio != numero:
            advertencias.append('El titular figura vinculado a otro grupo. Revisá el vínculo en el administrador.')
            persona = None
        elif persona is None:
            advertencias.append('No hay una persona titular vinculada a esta ficha.')
        familiares = list(Personas.objects.filter(numeroSocio=numero).order_by('relacionTitular', 'Cedula'))
    if can_personas and can_cuentas:
        from apps.usuarios.services.habilitacion import preparar_diagnosticos
        preparar_diagnosticos(familiares)
    cuenta = CuentaCorriente.objects.filter(socio_titular=socio).first() if can_cuentas else None
    context = {
        **admin.site.each_context(request), 'title': f'Ficha del socio {numero}',
        'socio': socio, 'persona': persona, 'familiares': familiares,
        'advertencias': advertencias, 'cuenta': cuenta, 'estado': None,
        'can_personas': can_personas, 'can_cuentas': can_cuentas,
        'can_cobrar': _puede_aplicar(request) and _puede(request, 'cobranzas.add_pago'),
        'can_aplicar': _puede_aplicar(request),
        'can_comprobantes': _puede(request, 'cobranzas.view_pago'),
        'embarcaciones': Embarcaciones.objects.filter(id_socio=numero).order_by('numero') if can_personas else [],
    }
    if cuenta:
        estado, cargos, pagos = movimientos_cuenta(cuenta)
        context.update(estado=estado,
            cargos_page=paginar(request, cargos, 'cargos_page', 'cargos'),
            pagos_page=paginar(request, pagos, 'pagos_page', 'pagos'),
            aplicaciones_page=paginar(request, AplicacionPago.objects.filter(
                pago__cuenta=cuenta, cargo__cuenta=cuenta).select_related(
                    'registrado_por', 'revertido_por').order_by('-created_at', '-pk'),
                'aplicaciones_page', 'aplicaciones'))
        if context['can_comprobantes']:
            recibos = dict(ComprobantePago.objects.filter(
                pago_id__in=[p.pk for p in context['pagos_page']]).values_list('pago_id', 'numero'))
            for pago in context['pagos_page']:
                pago.comprobante_numero = recibos.get(pago.pk)
    context['historial_page'] = describir_historial(paginar(
        request, historial_socio(socio, cuenta, comprobantes=context['can_comprobantes']), 'historial_page', 'historial'))
    return render(request, 'gestion/ficha_socio.html', context)


@login_required
@never_cache
def nuevo_cobro(request, numero):
    if not (_puede_aplicar(request) and _puede(request, 'cobranzas.add_pago')):
        raise PermissionDenied
    cuenta = get_object_or_404(CuentaCorriente.objects.select_related('socio_titular'), socio_titular_id=numero)
    return _flujo_cobro(request, cuenta)


@login_required
@never_cache
def aplicar_saldo_pago(request, pago_id):
    if not _puede_aplicar(request):
        raise PermissionDenied
    pago = get_object_or_404(Pago.objects.select_related('cuenta__socio_titular'), pk=pago_id)
    return _flujo_cobro(request, pago.cuenta, pago=pago)


REVIEW_SALT = 'gestion.cobro.confirmacion.v1'


def _flujo_cobro(request, cuenta, pago=None):
    form_class = SaldoForm if pago else CobroForm
    form = form_class(request.POST if request.method == 'POST' else None)
    propuesta = distribucion = resumen = token = None
    clave = request.POST.get('clave') or str(uuid4())
    disponible = pago.saldo_disponible if pago else None
    # Confirmation uses exactly the reviewed, signed payload. Repeated submissions
    # reach the service's idempotency check even if the payment now has no balance.
    if request.method == 'POST' and request.POST.get('confirmar'):
        try:
            datos = signing.loads(request.POST.get('revision', ''), salt=REVIEW_SALT, max_age=1800)
            if (datos['cuenta'] != cuenta.pk or datos['pago'] != (pago.pk if pago else None)
                    or datos['usuario'] != request.user.pk):
                raise signing.BadSignature
            form = form_class(datos['campos'])
            if not form.is_valid():
                raise ValidationError('Los datos del cobro no son válidos; vuelva a revisarlos.')
            kwargs = dict(usuario=request.user, clave=datos['clave'], aplicaciones=datos['aplicaciones'],
                          version=datos['version'], intencion_saldo=form.cleaned_data['intencion_saldo'])
            if pago:
                operation = aplicar_saldo(pago=pago, **kwargs)
            else:
                operation = confirmar_cobro(cuenta=cuenta, **kwargs,
                    **{key: value for key, value in form.cleaned_data.items() if key != 'intencion_saldo'})
        except signing.BadSignature:
            form.add_error(None, 'La confirmación venció o no es válida. Vuelva a revisar la distribución.')
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if pago:
                messages.success(request, f'Saldo aplicado al pago {pago.pk}. No se registró un nuevo ingreso. El comprobante original se conserva.')
                return redirect('gestion:ficha_socio', numero=cuenta.socio_titular_id)
            messages.success(request, f'Cobro registrado. Comprobante del pago {operation.pago_id}.')
            return redirect('gestion:comprobante_pago', pago_id=operation.pago_id)
    elif request.method == 'POST' and form.is_valid():
        disponible = disponible if pago else form.cleaned_data['importe_total']
        try:
            propuesta = proponer_aplicaciones(cuenta, disponible, pago=pago, usuario=request.user)
            revisar = request.POST.get('revisar')
            if revisar and request.POST.get('version') != propuesta['version']:
                raise ValidationError('La propuesta cambió; vuelva a revisar las aplicaciones.')
            distribucion = DistribucionForm(propuesta['filas'], disponible, request.POST if revisar or request.POST.get('editar') else None)
            if revisar and distribucion.is_valid():
                aplicaciones = distribucion.aplicaciones()
                restante = disponible - sum((Decimal(row['importe']) for row in aplicaciones), Decimal('0.00'))
                if restante > 0 and form.cleaned_data['intencion_saldo'] == 'SIN_CLASIFICAR':
                    raise ValidationError('Clasifique el saldo restante como anticipo o pendiente de aplicación.')
                campos = {key: str(value) for key, value in form.cleaned_data.items()}
                datos = {'cuenta': cuenta.pk, 'pago': pago.pk if pago else None, 'usuario': request.user.pk,
                         'clave': clave, 'campos': campos, 'aplicaciones': aplicaciones, 'version': propuesta['version']}
                token = signing.dumps(datos, salt=REVIEW_SALT, compress=True)
                por_id = {row['cargo_id']: row for row in propuesta['filas']}
                resumen = {'importe': disponible, 'restante': restante,
                           'filas': [{**por_id[row['cargo_id']], 'importe': row['importe']} for row in aplicaciones]}
        except ValidationError as exc:
            form.add_error(None, exc)
            propuesta = distribucion = None
    return render(request, 'gestion/cobro.html', {
        **admin.site.each_context(request),
        'title': f"{'Aplicar saldo' if pago else 'Registrar cobro'} · Socio {cuenta.socio_titular_id}",
        'socio': cuenta.socio_titular, 'cuenta': cuenta, 'pago': pago, 'disponible': disponible,
        'sin_saldo': pago is not None and disponible <= 0,
        'form': form, 'propuesta': propuesta, 'distribucion': distribucion,
        'resumen': resumen, 'revision': token, 'clave': clave,
        'campos_resumen': [(field.label, dict(getattr(field.field, 'choices', [])).get(field.value(), field.value())) for field in form],
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
