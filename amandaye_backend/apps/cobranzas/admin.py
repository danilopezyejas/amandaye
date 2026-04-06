from django.contrib import admin
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .services.cuentas import obtener_estado_cuenta

@admin.register(CuentaCorriente)
class CuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'socio_titular', 'tipo_cuenta', 'estado', 'fecha_apertura', 'deuda_vencida_display')
    list_filter = ('estado', 'tipo_cuenta')
    search_fields = ('socio_titular__numero', 'socio_titular__cedulaTitular')
    readonly_fields = ('fecha_apertura', 'fecha_cierre', 'created_at', 'updated_at', 'estado_cuenta_resumen')

    @admin.display(description="Deuda Vencida")
    def deuda_vencida_display(self, obj):
        res = obtener_estado_cuenta(obj)
        return f"${res['deuda_vencida']}"

    @admin.display(description="Resumen de Cuenta")
    def estado_cuenta_resumen(self, obj):
        from django.utils.html import format_html
        res = obtener_estado_cuenta(obj)
        
        estados_html = "<ul>"
        for est, cant in res.get('resumen_estados', {}).items():
            estados_html += f"<li>{est}: {cant}</li>"
        if not res.get('resumen_estados'):
            estados_html += "<li>Sin cargos</li>"
        estados_html += "</ul>"

        return format_html(
            "<strong>Saldo Total Pendiente:</strong> ${}<br>"
            "<strong>Deuda Vencida:</strong> ${}<br>"
            "<strong>Estado de Cargos:</strong>{}",
            res['saldo_total'], res['deuda_vencida'], format_html(estados_html)
        )

@admin.register(ConceptoCobro)
class ConceptoCobroAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo')
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
    list_display = ('id', 'pago', 'cargo', 'importe_aplicado', 'created_at')
    search_fields = ('pago__cuenta__socio_titular__numero',)
