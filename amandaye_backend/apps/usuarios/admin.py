from django.contrib import admin
from django.db.models import Q
from .models import (
    Embarcaciones,
    Historico_socios,
    Personas,
    Socios,
    Socios_cambios,
)

class HistorialValoresMixin:
    """
    Mixin para guardar en el historial (LogEntry) el valor anterior y el nuevo
    cuando se modifica un registro desde el Admin de Django.
    """
    def construct_change_message(self, request, form, formsets, add=False):
        change_message = super().construct_change_message(request, form, formsets, add)
        
        if not add and form.changed_data:
            changes = []
            for field in form.changed_data:
                old_val = form.initial.get(field)
                new_val = form.cleaned_data.get(field)

                # Intentar obtener la etiqueta descriptiva si el campo tiene 'choices' (ej: activo 1 -> ALTA)
                form_field = form.fields.get(field)
                if form_field and hasattr(form_field, 'choices'):
                    try:
                        choices_dict = dict(form_field.choices)
                        # Reemplazar con el valor legíble si existe en las opciones y no es un tipo complejo
                        if type(old_val) in [int, str, bool] and old_val in choices_dict:
                            old_val = choices_dict[old_val]
                        if type(new_val) in [int, str, bool] and new_val in choices_dict:
                            new_val = choices_dict[new_val]
                    except Exception:
                        pass

                if old_val in [None, '']: old_val = 'vacío'
                if new_val in [None, '']: new_val = 'vacío'
                
                # Obtener la etiqueta del campo, o usar el nombre de la variable como fallback
                field_label = form.fields[field].label if field in form.fields and form.fields[field].label else field
                changes.append(f'{field_label} (de "{old_val}" a "{new_val}")')
            
            if changes:
                for msg in change_message:
                    # Modificamos el mensaje estándar de django que lista solo los campos.
                    # Mantenemos la clave 'fields' porque Django asume que siempre existe para el mensaje de cambio.
                    if 'changed' in msg and 'fields' in msg['changed'] and 'object' not in msg['changed']:
                        msg['changed']['fields'] = changes
                        break

        return change_message

@admin.register(Personas)
class PersonasAdmin(HistorialValoresMixin, admin.ModelAdmin):
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
            ('3', 'RECHAZADO'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(activo=1)
        if self.value() == '0':
            return queryset.filter(activo=0)
        if self.value() == '2':
            return queryset.filter(activo=2)
        if self.value() == '3':
            return queryset.filter(activo=3)
        return queryset

@admin.register(Socios)
class SociosAdmin(HistorialValoresMixin, admin.ModelAdmin):
    list_display = ("numero", "cedula", "nombre_completo_socio", "tipo", "estado_activo", "tiene_cuenta", "fechaSolicitud", "fechaAprobacion", "fechaAlta")
    readonly_fields = ("fechaSolicitud", "fechaAprobacion", "fechaAlta", "fechaBaja")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'aprobar_socios_seleccionados' in actions and not request.user.has_perm('usuarios.puede_aprobar_socio'):
            del actions['aprobar_socios_seleccionados']
        if 'rechazar_socios_seleccionados' in actions and not request.user.has_perm('usuarios.puede_rechazar_socio'):
            del actions['rechazar_socios_seleccionados']
        if 'dar_baja_socios_seleccionados' in actions and not request.user.has_perm('usuarios.puede_dar_baja_socio'):
            del actions['dar_baja_socios_seleccionados']
        return actions

    @admin.display(description="Cuenta", boolean=True)
    def tiene_cuenta(self, obj):
        return hasattr(obj, 'cuenta_corriente') and obj.cuenta_corriente is not None

    @admin.action(description='Aprobar Socios Pendientes (Alta + Crear CC)')
    def aprobar_socios_seleccionados(self, request, queryset):
        from apps.usuarios.services.socios import aprobar_socio
        count = 0
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        errores = []
        for socio in queryset:
            try:
                aprobar_socio(socio)
                count += 1
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                errores.append(f"Socio {socio.numero}: {msg}")
            except Exception as e:
                errores.append(f"Socio {socio.numero}: {str(e)}")
                
        if count:
            self.message_user(request, f"{count} socios aprobados exitosamente.", level=messages.SUCCESS)
        if errores:
            for error in errores:
                self.message_user(request, error, level=messages.ERROR)

    @admin.action(description='Rechazar Solicitudes Pendientes')
    def rechazar_socios_seleccionados(self, request, queryset):
        from apps.usuarios.services.socios import rechazar_socio
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        count = 0
        errores = []
        for socio in queryset:
            try:
                rechazar_socio(socio, motivo="Rechazo masivo desde panel administrativo")
                count += 1
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                errores.append(f"Socio {socio.numero}: {msg}")
            except Exception as e:
                errores.append(f"Socio {socio.numero}: {str(e)}")
        if count:
            self.message_user(request, f"{count} solicitudes rechazadas.", level=messages.SUCCESS)
        if errores:
            for error in errores:
                self.message_user(request, error, level=messages.ERROR)

    @admin.action(description='Dar de Baja a Socios')
    def dar_baja_socios_seleccionados(self, request, queryset):
        from apps.usuarios.services.socios import dar_baja_socio
        count = 0
        from django.core.exceptions import ValidationError
        from django.contrib import messages
        errores = []
        for socio in queryset:
            try:
                dar_baja_socio(socio, motivo="Baja Administrativa masiva (Panel)")
                count += 1
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                errores.append(f"Socio {socio.numero}: {msg}")
            except Exception as e:
                errores.append(f"Socio {socio.numero}: {str(e)}")
                
        if count:
            self.message_user(request, f"{count} socios dados de baja exitosamente.", level=messages.SUCCESS)
        if errores:
            for error in errores:
                self.message_user(request, error, level=messages.ERROR)
    search_fields = ("numero", "cedulaTitular")
    list_filter = (EstadoActivoFilter, "tipo")

    def save_model(self, request, obj, form, change):
        if change and 'activo' in form.changed_data:
            viejo_activo = form.initial.get('activo')
            nuevo_activo = form.cleaned_data.get('activo')
            from django.contrib import messages

            if viejo_activo == 2 and nuevo_activo == 1:
                obj.activo = viejo_activo
                from apps.usuarios.services.socios import aprobar_socio
                try:
                    aprobar_socio(obj)
                    self.message_user(request, "Socio aprobado y Cuenta Corriente generada.", level=messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f"Error al aprobar: {str(e)}", level=messages.ERROR)
                return

            elif viejo_activo == 2 and nuevo_activo == 3:
                obj.activo = viejo_activo
                from apps.usuarios.services.socios import rechazar_socio
                try:
                    rechazar_socio(obj, motivo="Rechazo manual desde formulario")
                    self.message_user(request, "Solicitud rechazada correctamente.", level=messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f"Error al rechazar: {str(e)}", level=messages.ERROR)
                return

            elif viejo_activo in [1, 2] and nuevo_activo == 0:
                obj.activo = viejo_activo
                from apps.usuarios.services.socios import dar_baja_socio
                try:
                    dar_baja_socio(obj, motivo="Baja manual desde selector de formulario")
                    self.message_user(request, "Socio dado de baja correctamente.", level=messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f"Error dando de baja: {str(e)}", level=messages.ERROR)
                return

        super().save_model(request, obj, form, change)

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
            2: "PENDIENTE",
            3: "RECHAZADO",
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

    def delete_model(self, request, obj):
        # Cuando se elimina un socio, borramos el numero de socio (lo dejamos en 0) 
        # en las fichas de personas correspondientes
        Personas.objects.filter(numeroSocio=obj.numero).update(numeroSocio=0)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Mismo comportamiento pero para acciones masivas en la lista
        numeros = queryset.values_list('numero', flat=True)
        Personas.objects.filter(numeroSocio__in=numeros).update(numeroSocio=0)
        super().delete_queryset(request, queryset)


#admin.site.register(Embarcaciones)
#admin.site.register(Socios_cambios)

@admin.register(Historico_socios)
class HistoricoSociosAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'total', 'familiar', 'individual', 'personas')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)
    readonly_fields = ('fecha', 'total', 'familiar', 'individual', 'personas')
    actions = ['graficar_seleccionados']

    def has_add_permission(self, request):
        return False  # Los registros son generados automáticamente por el sistema

    @admin.action(description='Graficar registros seleccionados')
    def graficar_seleccionados(self, request, queryset):
        import json
        from django.shortcuts import render
        
        # Ordenar queryset por fecha para que el gráfico tenga sentido cronológico
        qs = queryset.order_by('fecha')
        
        fechas = [obj.fecha.strftime('%Y-%m-%d') for obj in qs]
        totales = [obj.total for obj in qs]
        familiares = [obj.familiar for obj in qs]
        individuales = [obj.individual for obj in qs]
        personas = [obj.personas or 0 for obj in qs]
        
        context = {
            'fechas_json': json.dumps(fechas),
            'totales_json': json.dumps(totales),
            'familiares_json': json.dumps(familiares),
            'individuales_json': json.dumps(individuales),
            'personas_json': json.dumps(personas),
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/usuarios/historico_socios/grafico.html', context)
