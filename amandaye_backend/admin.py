
from django.contrib import admin # type: ignore
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

admin.site.register(Embarcaciones)
admin.site.register(Historico_socios)
admin.site.register(Pagos)
class PersonasAdmin(admin.ModelAdmin):
    list_display = ('numeroSocio', 'nombre_completo', 'Cedula')

admin.site.register(Personas, PersonasAdmin)
admin.site.register(Precios)
admin.site.register(Recibos)
admin.site.register(Socios)
admin.site.register(Socios_cambios)

