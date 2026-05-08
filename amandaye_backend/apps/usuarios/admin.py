from django.contrib import admin
from django.db.models import Q
from .models import (
    Embarcaciones,
    Historico_socios,
    Personas,
    Socios,
    Socios_cambios,
    AprobacionProfesor,
    AvalComisionDirectiva,
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

class AprobacionProfesorInline(admin.TabularInline):
    model = AprobacionProfesor
    extra = 0
    can_delete = True
    exclude = ('numero_socio_momento', 'registrado_por')
    readonly_fields = ('created_at',)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django import forms
        if db_field.name == 'observaciones':
            kwargs['widget'] = forms.Textarea(attrs={'rows': 1, 'cols': 30, 'style': 'height: 2em;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

class AvalComisionDirectivaInline(admin.TabularInline):
    model = AvalComisionDirectiva
    extra = 0
    # Campos visibles en el inline
    fields = ('fecha_aval', 'observaciones', 'activo', 'motivo_revocacion', 'usuario_cd', 'fecha_revocacion', 'usuario_revocacion')
    # Los campos de auditoría se llenan automáticamente — solo lectura
    readonly_fields = ('usuario_cd', 'fecha_revocacion', 'usuario_revocacion')
    verbose_name = 'Aval de Comisión Directiva'
    verbose_name_plural = 'Avales de Comisión Directiva'

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        # Si no tiene permiso de revocar, no puede editar activo ni el motivo
        if not request.user.has_perm('usuarios.puede_revocar_aval'):
            ro.extend(['activo', 'motivo_revocacion'])
        return ro

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django import forms
        if db_field.name in ['observaciones', 'motivo_revocacion']:
            kwargs['widget'] = forms.Textarea(attrs={'rows': 1, 'cols': 30, 'style': 'height: 2em;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

class EstadoHabilitacionFilter(admin.SimpleListFilter):
    title = 'estado de habilitación'
    parameter_name = 'estado_habilitacion'

    def lookups(self, request, model_admin):
        return Personas.ESTADO_HABILITACION

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(estado_habilitacion=self.value())
        return queryset

@admin.register(Personas)
class PersonasAdmin(HistorialValoresMixin, admin.ModelAdmin):
    readonly_fields = ("enlace_al_titular", "edad_calculada", "estado_habilitacion", "fecha_ultimo_calculo_habilitacion", "diagnostico_habilitacion")
    inlines = [AprobacionProfesorInline, AvalComisionDirectivaInline]
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
    fieldsets = (
        ('Vínculos y Estado', {
            'fields': ('enlace_al_titular', 'estado_habilitacion', 'diagnostico_habilitacion'),
        }),
        ('Datos Personales', {
            'fields': (
                'Cedula', 'numeroSocio', 'relacionTitular',
                ('PrimerNombre', 'SegundoNombre'),
                ('PrimerApellido', 'SegundoApellido'),
                'FechaNacimiento', 'edad_calculada'
            ),
        }),
        ('Contacto', {
            'fields': ('Direccion', 'Telefono', 'Celular', 'Correo'),
        }),
        ('Otros Datos', {
            'fields': ('salud', 'llave'),
        }),
    )
    list_display = ("nro_socio", "nombre_completo", "cedula_display", "estado_habilitacion_colorido")
    list_filter = (EstadoHabilitacionFilter,)
    search_fields = ("Cedula", "PrimerNombre", "PrimerApellido", "SegundoApellido", "numeroSocio")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, AvalComisionDirectiva):
                if not getattr(instance, 'pk', None):
                    instance.usuario_cd = request.user
            elif isinstance(instance, AprobacionProfesor):
                if not getattr(instance, 'pk', None):
                    instance.registrado_por = request.user
            instance.save()
        formset.save_m2m()

    @admin.display(description="Diagnóstico de habilitación")
    def diagnostico_habilitacion(self, obj):
        import datetime
        from django.utils.html import format_html, mark_safe
        from apps.usuarios.models import Socios

        if obj.estado_habilitacion != 'NO_HABILITADO':
            return "-"

        hoy = datetime.date.today()
        socio = Socios.objects.filter(numero=obj.numeroSocio).select_related('cuenta_corriente').first()

        faltantes = []

        if not socio:
            return format_html(
                '<span style="color:#c0392b;">⚠ No tiene un socio registrado con el número {}.</span>',
                obj.numeroSocio
            )

        # cond_a: socio activo (Alta)
        if socio.activo != 1:
            estado_label = dict(Socios.ACTIVO_CHOICES).get(socio.activo, socio.activo)
            faltantes.append(f'El socio no está en ALTA (estado actual: <b>{estado_label}</b>)')

        # cond_b: no es TEMPORADA
        if socio.tipo_cuota == 'TEMPORADA':
            faltantes.append('El tipo de cuota es <b>Temporada</b> (no otorga habilitación permanente)')

        # cond_c: mayor de edad
        if obj.FechaNacimiento:
            edad = hoy.year - obj.FechaNacimiento.year - (
                (hoy.month, hoy.day) < (obj.FechaNacimiento.month, obj.FechaNacimiento.day)
            )
            if edad < 18:
                faltantes.append(f'Es menor de edad (<b>{edad} años</b>; se requieren 18)')
        else:
            faltantes.append('No tiene fecha de nacimiento registrada')

        # La antigüedad y aprobaciones se calculan desde el inicio del PERIODO ACTUAL (fechaAlta)
        fecha_base = socio.fechaAlta or socio.fechaAprobacion

        # cond_d: antigüedad >= 365 días desde el alta actual
        if fecha_base:
            dias = (hoy - fecha_base).days
            if dias < 365:
                faltantes.append(f'Antigüedad insuficiente (<b>{dias} días</b>; se requieren 365 desde el Alta)')
        else:
            faltantes.append('No tiene fecha de alta registrada')

        # cond_e: aprobación de profesor post-aprobación
        tiene_aprobacion = False
        if fecha_base:
            for ap in obj.aprobaciones_profesor.all():
                if ap.fecha >= fecha_base and ap.numero_socio_momento == socio.numero:
                    tiene_aprobacion = True
                    break
        if not tiene_aprobacion:
            faltantes.append('Falta <b>aprobación de profesor</b> posterior a la fecha de Alta actual')

        # cond_f: aval activo de CD
        if not any(av.activo for av in obj.avales_cd.all()):
            faltantes.append('Falta <b>aval activo de Comisión Directiva</b>')

        if not faltantes:
            return mark_safe('<span style="color: green;">✔ Cumple todas las condiciones — recalcular para actualizar estado.</span>')

        items = ''.join(f'<li style="margin-bottom:4px;">❌ {f}</li>' for f in faltantes)
        return format_html(
            '<ul style="margin:0; padding-left:18px; color:#c0392b;">{}</ul>',
            mark_safe(items)
        )

    @admin.display(description="Estado Habilitación", ordering="estado_habilitacion")
    def estado_habilitacion_colorido(self, obj):
        from django.utils.html import format_html
        colores = {
            'HABILITADO': 'green',
            'SUSPENDIDO': 'orange',
            'REVOCADO': 'red',
            'NO_HABILITADO': 'gray'
        }
        color = colores.get(obj.estado_habilitacion, 'gray')
        
        # Inyectamos el CSS del tooltip directamente aquí para asegurar que se cargue
        # Esto es un respaldo por si el archivo .css externo tiene problemas de caché
        css_inline = mark_safe("""
        <style>
            .inline-group td.delete { position: relative !important; }
            .inline-group td.delete:hover::after {
                content: "Eliminar este registro" !important;
                position: absolute !important;
                bottom: 100% !important;
                right: 10px !important;
                background: #c0392b !important;
                color: #fff !important;
                padding: 5px 10px !important;
                border-radius: 4px !important;
                font-size: 12px !important;
                white-space: nowrap !important;
                z-index: 99999 !important;
                margin-bottom: 8px !important;
                display: block !important;
            }
            .inline-group .delete a, .inline-group .delete label {
                color: #e74c3c !important;
                font-weight: bold !important;
            }
        </style>
        """)
        return format_html('{}{}<span style="color: {}; font-weight: bold;">{}</span>', css_inline, "", color, obj.get_estado_habilitacion_display())

    @admin.display(description="Vínculo con Socio/Titular")
    def enlace_al_titular(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        
        if not obj or not obj.numeroSocio or obj.numeroSocio <= 0:
            return format_html('<span style="color: #7f8c8d; font-style: italic;">Persona no vinculada a un socio activo.</span>')

        socio = Socios.objects.filter(numero=obj.numeroSocio).first()
        if not socio:
            return format_html('<span style="color: #c0392b;">⚠️ No se encontró el Socio Nº {} en el sistema.</span>', obj.numeroSocio)
            
        # Caso A: La persona actual ES el titular del socio
        if obj.Cedula == socio.cedulaTitular:
            url_socio = reverse('admin:usuarios_socios_change', args=[socio.numero])
            return format_html(
                '<div style="margin-bottom: 5px;">'
                '<span style="display: block; margin-bottom: 5px; color: #2c3e50; font-weight: bold;">Usted es el TITULAR de esta membresía:</span>'
                '<a href="{}" class="button" style="background: #e67e22; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; display: inline-block;">'
                '💳 Ver Ficha de Socio (Nº {})'
                '</a>'
                '</div>',
                url_socio, socio.numero
            )
            
        # Caso B: La persona actual es un FAMILIAR, buscamos al titular
        persona_titular = Personas.objects.filter(Cedula=socio.cedulaTitular).first()
        if persona_titular:
            url_titular = reverse('admin:usuarios_personas_change', args=[persona_titular.Cedula])
            return format_html(
                '<div style="margin-bottom: 5px;">'
                '<span style="display: block; margin-bottom: 5px; color: #2c3e50; font-weight: bold;">Usted es FAMILIAR del socio titular:</span>'
                '<a href="{}" class="button" style="background: #2980b9; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; display: inline-block;">'
                '👤 Ver ficha del Titular ({} - C.I. {})'
                '</a>'
                '</div>',
                url_titular, persona_titular.nombre_completo(), persona_titular.Cedula
            )
            
        return format_html('<span style="color: #e67e22;">Socio Nº {} (Titular C.I. {} no encontrado en Personas)</span>', socio.numero, socio.cedulaTitular)

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
    list_display = ("numero", "cedula", "nombre_completo_socio", "tipo_socio", "tipo_cuota", "estado_activo", "tiene_cuenta", "fechaSolicitud", "fechaAprobacion", "fechaAlta", "fechaBaja")
    readonly_fields = ("enlace_a_persona", "fechaSolicitud", "fechaAprobacion", "fechaAlta", "fechaBaja")
    
    fieldsets = (
        ('Navegación Rápida', {
            'fields': ('enlace_a_persona',),
        }),
        ('Información Básica', {
            'fields': ('numero', 'cedulaTitular', 'activo', 'tipo_socio', 'tipo_cuota'),
        }),
        ('Fechas de Gestión', {
            'fields': ('fechaSolicitud', 'fechaAprobacion', 'fechaAlta', 'fechaBaja'),
        }),
        ('Otros', {
            'fields': ('percha', 'comentarios'),
        }),
    )

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
    list_filter = (EstadoActivoFilter, "tipo_socio", "tipo_cuota")

    def save_model(self, request, obj, form, change):
        from django.contrib import messages

        if change:
            try:
                db_obj = Socios.objects.get(pk=obj.pk)
                viejo_activo = db_obj.activo
            except Socios.DoesNotExist:
                viejo_activo = None

            nuevo_activo = obj.activo

            if viejo_activo != nuevo_activo:

                # PENDIENTE → ALTA: aprobación completa (crea CC y cargos)
                if viejo_activo == 2 and nuevo_activo == 1:
                    from apps.usuarios.services.socios import aprobar_socio
                    try:
                        aprobar_socio(db_obj)
                        self.message_user(request, "Socio aprobado y Cuenta Corriente generada.", level=messages.SUCCESS)
                    except Exception as e:
                        self.message_user(request, f"Error al aprobar: {str(e)}", level=messages.ERROR)
                    return

                # BAJA → ALTA: reactivación (reabre CC existente)
                elif viejo_activo == 0 and nuevo_activo == 1:
                    from apps.usuarios.services.socios import reactivar_socio
                    try:
                        reactivar_socio(db_obj, motivo="Reactivación manual desde formulario")
                        self.message_user(request, "Socio reactivado correctamente.", level=messages.SUCCESS)
                    except Exception as e:
                        self.message_user(request, f"Error al reactivar: {str(e)}", level=messages.ERROR)
                    return

                # PENDIENTE → RECHAZADO
                elif viejo_activo == 2 and nuevo_activo == 3:
                    from apps.usuarios.services.socios import rechazar_socio
                    try:
                        rechazar_socio(db_obj, motivo="Rechazo manual desde formulario")
                        self.message_user(request, "Solicitud rechazada correctamente.", level=messages.SUCCESS)
                    except Exception as e:
                        self.message_user(request, f"Error al rechazar: {str(e)}", level=messages.ERROR)
                    return

                # ALTA/PENDIENTE → BAJA
                elif viejo_activo in [1, 2] and nuevo_activo == 0:
                    from apps.usuarios.services.socios import dar_baja_socio
                    try:
                        dar_baja_socio(db_obj, motivo="Baja manual desde selector de formulario")
                        self.message_user(request, "Socio dado de baja correctamente.", level=messages.SUCCESS)
                    except Exception as e:
                        self.message_user(request, f"Error dando de baja: {str(e)}", level=messages.ERROR)
                    return

        super().save_model(request, obj, form, change)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django import forms
        if db_field.name == 'comentarios':
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

    @admin.display(description="Ficha de Persona")
    def enlace_a_persona(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        
        # Obtenemos la persona titular
        persona = self.get_persona(obj)
        if persona:
            url = reverse('admin:usuarios_personas_change', args=[persona.Cedula])
            return format_html(
                '<a href="{}" class="button" style="background: #34495e; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">'
                '📂 Ver ficha de Persona'
                '</a>',
                url
            )
        return "-"

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
