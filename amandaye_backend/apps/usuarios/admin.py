from django.contrib import admin
from django.db.models import Q
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
    readonly_fields = ("enlace_al_titular", "edad_calculada")
    fields = (
        "Cedula",
        "numeroSocio",
        "PrimerNombre",
        "SegundoNombre",
        "PrimerApellido",
        "SegundoApellido",
        "FechaNacimiento",
        "edad_calculada",
        "Direccion",
        "Telefono",
        "Celular",
        "Correo",
        "relacionTitular",
        "salud",
        "llave",
        "enlace_al_titular"
    )
    list_display = ("nro_socio", "nombre_completo", "cedula_display")
    search_fields = ("Cedula", "PrimerNombre", "PrimerApellido", "SegundoApellido", "numeroSocio")

    @admin.display(description="Socio Titular")
    def enlace_al_titular(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        
        if not obj or not obj.Cedula:
            return "Datos insuficientes."

        socio = Socios.objects.filter(numero=obj.numeroSocio).first()
        if not socio:
            return "Número de socio no registrado/activo."
            
        if obj.Cedula == socio.cedulaTitular:
            url_socio = reverse('admin:usuarios_socios_change', args=[socio.numero])
            return format_html(
                '<a href="{}" style="background-color: #ed6c06; color: white; padding: 8px 14px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #c95b04;">Ir a Ficha de Socio (Nº {})</a>',
                url_socio, socio.numero
            )
            
        persona_titular = Personas.objects.filter(Cedula=socio.cedulaTitular).first()
        if persona_titular:
            url = reverse('admin:usuarios_personas_change', args=[persona_titular.Cedula])
            return format_html(
                '<a href="{}" style="background-color: #1e489c; color: white; padding: 8px 14px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #0f296d;">Ir a ficha del Titular ({} - C.I. {})</a>',
                url, persona_titular.nombre_completo(), persona_titular.Cedula
            )
        return "Titular externo o no encontrado en la base de datos."

    @admin.display(description="Edad")
    def edad_calculada(self, obj):
        from datetime import date
        from django.utils.html import format_html

        if not obj or not obj.FechaNacimiento:
            return "Sin fecha de nacimiento"

        today = date.today()
        # Calcula la edad teniendo en cuenta que no haya pasado el cumpleaños en este año
        edad = today.year - obj.FechaNacimiento.year - ((today.month, today.day) < (obj.FechaNacimiento.month, obj.FechaNacimiento.day))

        # Chequear relación de titularidad para inyectar advertencia
        if obj.relacionTitular:
            rel = obj.relacionTitular.strip().lower()
            if rel == "hijo" and edad >= 18:
                return format_html(
                    '<strong style="color: #ff0000; font-size: 1.1em;">{} años (ADVERTENCIA: Es hijo/a y tiene 18 años o más)</strong>',
                    edad
                )
        return f"{edad} años"

    @admin.display(description="NÚMERO DE SOCIO", ordering="numeroSocio")
    def nro_socio(self, obj):
        return obj.numeroSocio

    @admin.display(description="CÉDULA", ordering="Cedula")
    def cedula_display(self, obj):
        return obj.Cedula


class EstadoActivoFilter(admin.SimpleListFilter):
    title = 'estado activo'
    parameter_name = 'activo'

    def lookups(self, request, model_admin):
        return (
            ('1', 'ALTA'),
            ('0', 'BAJA'),
            ('2', 'PENDIENTE'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(activo=1)
        if self.value() == '0':
            return queryset.filter(activo=0)
        if self.value() == '2':
            return queryset.filter(activo=2)
        return queryset

@admin.register(Socios)
class SociosAdmin(admin.ModelAdmin):
    list_display = ("numero", "cedula", "nombre_completo_socio", "tipo", "estado_activo")
    search_fields = ("numero", "cedulaTitular")
    list_filter = (EstadoActivoFilter, "tipo")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django import forms
        if db_field.name == 'tipo':
            kwargs['widget'] = forms.TextInput(attrs={'size': '30'})
        elif db_field.name == 'comentarios':
            kwargs['widget'] = forms.Textarea(attrs={'rows': 4, 'cols': 60})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="ACTIVO", ordering="activo")
    def estado_activo(self, obj):
        estados = {
            1: "ALTA",
            0: "BAJA",
            2: "PENDIENTE"
        }
        return estados.get(obj.activo, "-")

    @admin.display(description="CEDULA", ordering="cedulaTitular")
    def cedula(self, obj):
        return obj.cedulaTitular

    def get_search_results(self, request, queryset, search_term):
        # 1. Ejecutar la búsqueda estándar que busca por 'numero' o 'cedulaTitular' exacto
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        # 2. Si el usuario ingresó algo, buscar también el nombre en la tabla 'Personas'
        if search_term:
            q_objects = Q()
            # Dividir la frase por los espacios para buscar múltiples palabras (ej. "Juan Pérez")
            for word in search_term.split():
                q_word = (
                    Q(PrimerNombre__icontains=word) |
                    Q(SegundoNombre__icontains=word) |
                    Q(PrimerApellido__icontains=word) |
                    Q(SegundoApellido__icontains=word)
                )
                # Encadenamos con AND, exigiendo que cada palabra esté presente en alguna parte
                q_objects &= q_word

            personas_coincidentes = Personas.objects.filter(q_objects)
            # Extraer solo las cédulas de los que coincidieron
            cedulas = personas_coincidentes.values_list('Cedula', flat=True)
            
            # Combinar el queryset existente con los que coincide la cédula
            if cedulas:
                queryset |= self.model.objects.filter(cedulaTitular__in=cedulas)
                
        return queryset, use_distinct

    def get_persona(self, obj):
        if not hasattr(obj, '_persona_cache'):
            # Buscar la Persona correspondiente a este Socio
            persona = Personas.objects.filter(Cedula=obj.cedulaTitular).first()
            obj._persona_cache = persona
        return obj._persona_cache

    @admin.display(description="Nombre Completo")
    def nombre_completo_socio(self, obj):
        p = self.get_persona(obj)
        return p.nombre_completo() if p else ""


#admin.site.register(Embarcaciones)
#admin.site.register(Historico_socios)
admin.site.register(Pagos)
#admin.site.register(Precios)
#admin.site.register(Recibos)
#admin.site.register(Socios_cambios)
