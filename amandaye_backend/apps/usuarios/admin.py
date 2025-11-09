from django.contrib import admin
from .models import (
    Embarcaciones,
    Historico_socios,
    Pagos,
    Personas,
    Precios,
    Recibos,
    Socios,
    Socios_cambios,
)

@admin.register(Personas)
class PersonasAdmin(admin.ModelAdmin):
    list_display = ("numeroSocio", "nombre_completo", "Cedula")
    search_fields = ("Cedula", "PrimerNombre", "PrimerApellido", "SegundoApellido")


@admin.register(Socios)
class SociosAdmin(admin.ModelAdmin):
    list_display = ("numero", "cedulaTitular", "tipo", "fechaAlta", "activo")
    search_fields = ("numero", "cedulaTitular")
    list_filter = ("activo", "tipo")


admin.site.register(Embarcaciones)
admin.site.register(Historico_socios)
admin.site.register(Pagos)
admin.site.register(Precios)
admin.site.register(Recibos)
admin.site.register(Socios_cambios)
