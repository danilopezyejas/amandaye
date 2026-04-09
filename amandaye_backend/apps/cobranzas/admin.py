from django.contrib import admin
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .services.cuentas import obtener_estado_cuenta

@admin.register(CuentaCorriente)
class CuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'socio_titular', 'tipo_cuenta', 'estado', 'fecha_apertura', 'deuda_vencida_display', 'estado_cuenta_display')
    list_filter = ('estado', 'tipo_cuenta')
    search_fields = ('socio_titular__numero', 'socio_titular__cedulaTitular')
    readonly_fields = ('fecha_apertura', 'fecha_cierre', 'created_at', 'updated_at', 'estado_cuenta_resumen')

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            from apps.usuarios.models import Personas
            from django.db.models import Q
            # Buscar personas que coincidan con el texto
            personas_qs = Personas.objects.filter(
                Q(PrimerNombre__icontains=search_term) |
                Q(PrimerApellido__icontains=search_term) |
                Q(SegundoNombre__icontains=search_term) |
                Q(SegundoApellido__icontains=search_term)
            ).values_list('Cedula', flat=True)
            # Agregar a las cuentas cuyos socios tengan esas cédulas
            queryset |= self.model.objects.filter(socio_titular__cedulaTitular__in=personas_qs)
        return queryset, use_distinct

    @admin.display(description="Deuda Vencida")
    def deuda_vencida_display(self, obj):
        res = obtener_estado_cuenta(obj)
        return f"${res['deuda_vencida']}"

    @admin.display(description="Estado Cuenta")
    def estado_cuenta_display(self, obj):
        res = obtener_estado_cuenta(obj)
        colores = {
            'AL_DIA': '#2e7d32',
            'CON_DEUDA': '#e65100',
            'MOROSO': '#b71c1c',
        }
        ec = res.get('estado_cuenta', '-')
        color = colores.get(ec, '#333')
        from django.utils.html import format_html
        return format_html('<strong style="color: {};">{}</strong>', color, ec)

    @admin.display(description="Resumen de Cuenta")
    def estado_cuenta_resumen(self, obj):
        from django.utils.html import format_html
        res = obtener_estado_cuenta(obj)

        estados_html = ""
        for est, cant in res.get('resumen_estados', {}).items():
            estados_html += f"<br>&nbsp;&nbsp;&nbsp;&nbsp;• {est}: {cant}"
        if not res.get('resumen_estados'):
            estados_html += "<br>&nbsp;&nbsp;&nbsp;&nbsp;• Sin cargos"

        ec = res.get('estado_cuenta', '-')
        colores = {'AL_DIA': '#2e7d32', 'CON_DEUDA': '#e65100', 'MOROSO': '#b71c1c'}
        color = colores.get(ec, '#333')

        return format_html(
            "<strong>Estado:</strong> <strong style=\"color: {}\">{}</strong><br>"
            "<strong>Saldo Total Pendiente:</strong> ${}<br>"
            "<strong>Deuda Vencida:</strong> ${}<br>"
            "<strong>Estado de Cargos:</strong>{}",
            color, ec, res['saldo_total'], res['deuda_vencida'], format_html(estados_html)
        )

class AplicacionPagoInline(admin.TabularInline):
    model = AplicacionPago
    extra = 0
    can_delete = False
    readonly_fields = ('pago', 'cargo', 'importe_aplicado', 'estado', 'fecha_reversion')
    fields = ('cargo', 'importe_aplicado', 'estado', 'fecha_reversion')
    
    def has_add_permission(self, request, obj):
        return False

@admin.register(ConceptoCobro)
class ConceptoCobroAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'importe_por_defecto', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'nombre')

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuenta', 'concepto', 'periodo', 'importe', 'estado', 'fecha_vencimiento')
    list_filter = ('estado', 'concepto', 'periodo')
    search_fields = ('cuenta__socio_titular__numero',)
    readonly_fields = ('total_aplicado', 'saldo_pendiente', 'esta_vencido')
    inlines = [AplicacionPagoInline]
    actions = ['anular_cargos_seleccionados']

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'anular_cargos_seleccionados' in actions and not request.user.has_perm('cobranzas.puede_anular_cargo'):
            del actions['anular_cargos_seleccionados']
        return actions

    @admin.action(description='Anular cargos seleccionados')
    def anular_cargos_seleccionados(self, request, queryset):
        from apps.cobranzas.services.cargos import anular_cargo
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        count = 0
        errores = []
        for cargo in queryset:
            try:
                anular_cargo(cargo, observaciones="Anulación masiva desde panel administrativo")
                count += 1
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                errores.append(f"Cargo {cargo.id}: {msg}")
        if count:
            self.message_user(request, f"{count} cargos anulados exitosamente.", level=messages.SUCCESS)
        if errores:
            for error in errores:
                self.message_user(request, error, level=messages.ERROR)


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_filter = ('medio_pago', 'fecha_pago')
    search_fields = ('cuenta__socio_titular__numero', 'referencia')
    autocomplete_fields = ['cuenta']
    inlines = [AplicacionPagoInline]

    def get_list_display(self, request):
        base = ('id', 'cuenta', 'fecha_pago', 'importe_total', 'total_aplicado', 'saldo_disponible', 'medio_pago')
        if request.user.has_perm('cobranzas.puede_aplicar_pago'):
            return base + ('aplicar_pago_link',)
        return base

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'cuenta' in form.base_fields:
            form.base_fields['cuenta'].widget.can_add_related = False
            form.base_fields['cuenta'].widget.can_change_related = False
            form.base_fields['cuenta'].widget.can_delete_related = False
            form.base_fields['cuenta'].widget.can_view_related = False
        return form

    def get_readonly_fields(self, request, obj=None):
        base_readonly = ['total_aplicado', 'saldo_disponible']
        if request.user.has_perm('cobranzas.puede_aplicar_pago'):
            base_readonly.append('aplicar_pago_link_ficha')
        if obj:
            base_readonly.extend(['cuenta', 'fecha_pago', 'importe_total', 'medio_pago'])
        return tuple(base_readonly)

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and request.user.has_perm('cobranzas.puede_aplicar_pago'):
            if 'aplicar_pago_link_ficha' not in fields:
                fields = ['aplicar_pago_link_ficha'] + [f for f in fields if f != 'aplicar_pago_link_ficha']
        elif 'aplicar_pago_link_ficha' in fields:
            fields.remove('aplicar_pago_link_ficha')
        return fields

    @admin.display(description="Acción: Aplicar Saldo")
    def aplicar_pago_link_ficha(self, obj):
        if obj and obj.saldo_disponible > 0:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:cobranzas_pago_aplicar', args=[obj.pk])
            return format_html('<a class="button" style="background-color: #2e7d32; color: white; padding: 10px 15px; font-weight: bold; border-radius: 4px;" href="{}">🟢 Aplicar saldo a cargo</a>', url)
        return "Sin saldo disponible"

    @admin.display(description="Aplicar Saldo")
    def aplicar_pago_link(self, obj):
        if obj.saldo_disponible > 0:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:cobranzas_pago_aplicar', args=[obj.pk])
            return format_html('<a class="button" style="background-color: #2e7d32; color: white;" href="{}">Aplicar a Cargo</a>', url)
        return "-"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:pago_id>/aplicar/', self.admin_site.admin_view(self.aplicar_pago_view), name='cobranzas_pago_aplicar'),
        ]
        return custom_urls + urls

    def aplicar_pago_view(self, request, pago_id):
        from django.core.exceptions import PermissionDenied
        if not request.user.has_perm('cobranzas.puede_aplicar_pago'):
            raise PermissionDenied("No tienes permisos para aplicar pagos.")
        from django.shortcuts import get_object_or_404, render, redirect
        from apps.cobranzas.services.pagos import aplicar_pago
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        from decimal import Decimal

        pago = get_object_or_404(Pago, pk=pago_id)
        
        if request.method == 'POST':
            cargo_id = request.POST.get('cargo_id')
            importe = request.POST.get('importe')
            if cargo_id and importe:
                try:
                    cargo = Cargo.objects.get(pk=cargo_id)
                    aplicar_pago(pago, cargo, Decimal(importe))
                    messages.success(request, f"Se aplicaron ${importe} al cargo {cargo_id} exitosamente.")
                    return redirect('admin:cobranzas_pago_change', pago.pk)
                except ValidationError as e:
                    messages.error(request, getattr(e, 'message', str(e)))
                except Exception as e:
                    messages.error(request, f"Error inesperado: {str(e)}")
            else:
                messages.error(request, "Debe seleccionar un cargo y un importe válidos.")

        cargos_pendientes = Cargo.objects.filter(cuenta=pago.cuenta).exclude(estado=Cargo.Estado.ANULADO).exclude(estado=Cargo.Estado.PAGADO)
        
        context = dict(
            self.admin_site.each_context(request),
            title=f"Aplicar Saldo del Pago {pago.id}",
            pago=pago,
            cargos=cargos_pendientes,
        )
        return render(request, 'admin/cobranzas/pago/aplicar_pago.html', context)


@admin.register(AplicacionPago)
class AplicacionPagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pago', 'cargo', 'importe_aplicado', 'estado', 'fecha_reversion', 'created_at')
    list_filter = ('estado',)
    search_fields = ('pago__cuenta__socio_titular__numero',)
    readonly_fields = ('pago', 'cargo', 'importe_aplicado', 'estado', 'fecha_reversion', 'motivo_reversion', 'created_at', 'updated_at')
    actions = ['revertir_aplicaciones']

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'revertir_aplicaciones' in actions and not request.user.has_perm('cobranzas.puede_revertir_aplicacion_pago'):
            del actions['revertir_aplicaciones']
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Revertir aplicaciones seleccionadas')
    def revertir_aplicaciones(self, request, queryset):
        from apps.cobranzas.services.pagos import revertir_aplicacion
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        from django.shortcuts import render
        from django.http import HttpResponseRedirect
        
        if request.POST.get('post'):
            motivo = request.POST.get('motivo_reversion', 'Reversión desde panel administrativo')
            count = 0
            for aplicacion in queryset:
                try:
                    revertir_aplicacion(aplicacion, motivo=motivo)
                    count += 1
                except ValidationError as e:
                    msg = e.message if hasattr(e, 'message') else str(e)
                    self.message_user(request, f"Error en Aplicación {aplicacion.id}: {msg}", level=messages.ERROR)
            if count:
                 self.message_user(request, f"{count} aplicaciones revertidas exitosamente.", level=messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
            
        import admin
        context = dict(
           self.admin_site.each_context(request),
           title="Confirmar Reversión de Aplicaciones",
           queryset=queryset,
           action_checkbox_name=admin.helpers.ACTION_CHECKBOX_NAME,
        )
        return render(request, 'admin/cobranzas/aplicacionpago/revertir_confirmacion.html', context)
