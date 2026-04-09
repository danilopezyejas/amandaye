from django.contrib import admin
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .services.cuentas import obtener_estado_cuenta

@admin.register(CuentaCorriente)
class CuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'socio_titular', 'tipo_cuenta', 'estado', 'fecha_apertura', 'deuda_vencida_display', 'estado_cuenta_display')
    list_filter = ('estado', 'tipo_cuenta')
    search_fields = ('socio_titular__numero', 'socio_titular__cedulaTitular')
    readonly_fields = ('fecha_apertura', 'fecha_cierre', 'created_at', 'updated_at', 'estado_cuenta_resumen')

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

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuenta', 'fecha_pago', 'importe_total', 'medio_pago')
    list_filter = ('medio_pago', 'fecha_pago')
    search_fields = ('cuenta__socio_titular__numero', 'referencia')
    readonly_fields = ('total_aplicado', 'saldo_disponible')

@admin.register(AplicacionPago)
class AplicacionPagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pago', 'cargo', 'importe_aplicado', 'estado', 'fecha_reversion', 'created_at')
    list_filter = ('estado',)
    search_fields = ('pago__cuenta__socio_titular__numero',)
    readonly_fields = ('estado', 'fecha_reversion', 'motivo_reversion', 'created_at', 'updated_at')
