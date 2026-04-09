from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.usuarios.models import Socios, Personas
from apps.cobranzas.models import CuentaCorriente, Cargo, Pago, AplicacionPago, ConceptoCobro

class Command(BaseCommand):
    help = 'Crea los grupos base del sistema y asigna los permisos correspondientes (idempotente)'

    def handle(self, *args, **kwargs):
        grupos_config = {
            'Administrador': 'all',  # Tendrá todos los permisos
            
            'Comision Directiva': {
                'modelos': {
                    Socios: ['view'],
                    Personas: ['view'],
                    CuentaCorriente: ['view'],
                    Cargo: ['view'],
                    Pago: ['view'],
                    AplicacionPago: ['view'],
                    ConceptoCobro: ['view']
                },
                'custom': [
                    'puede_aprobar_socio',
                    'puede_rechazar_socio',
                    'puede_dar_baja_socio',
                    'puede_ver_resumen_cobranzas'
                ]
            },
            
            'Secretaria': {
                'modelos': {
                    Socios: ['view', 'add', 'change'],
                    Personas: ['view', 'add', 'change'],
                    CuentaCorriente: ['view'],
                    Cargo: ['view'],
                    Pago: ['view', 'add'],
                    AplicacionPago: ['view'],
                },
                'custom': [
                    'puede_aplicar_pago'
                ]
            },
            
            'Tesoreria': {
                'modelos': {
                    Socios: ['view'],
                    Personas: ['view'],
                    CuentaCorriente: ['view'],
                    Cargo: ['view', 'change'],  # Necesitan change si anulan cargos con el admin estandar de edicion
                    Pago: ['view', 'add', 'change'],
                    AplicacionPago: ['view'],
                },
                'custom': [
                    'puede_aplicar_pago',
                    'puede_revertir_aplicacion_pago',
                    'puede_anular_cargo',
                    'puede_ver_resumen_cobranzas'
                ]
            }
        }

        # Clear existing permissions from our targeted groups to be truly idempotent when roles change
        for nombre_grupo in grupos_config.keys():
            grupo, created = Group.objects.get_or_create(name=nombre_grupo)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Grupo "{nombre_grupo}" creado.'))
            grupo.permissions.clear()
            
            if grupos_config[nombre_grupo] == 'all':
                grupo.permissions.set(Permission.objects.all())
                self.stdout.write(self.style.SUCCESS(f'Todos los permisos asignados a "Administrador".'))
                continue

            config = grupos_config[nombre_grupo]
            perms_to_add = []

            # 1. Standard Django Model Permissions
            for modelo, acciones in config['modelos'].items():
                ct = ContentType.objects.get_for_model(modelo)
                for accion in acciones:
                    codename = f"{accion}_{modelo._meta.model_name}"
                    try:
                        perm = Permission.objects.get(codename=codename, content_type=ct)
                        perms_to_add.append(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'No se encontró el permiso estándar: {codename}'))

            # 2. Custom Permissions
            for codename in config['custom']:
                try:
                    # Custom perms are scattered through the app content types, let's just query by codename:
                    perm = Permission.objects.get(codename=codename)
                    perms_to_add.append(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'CRITICAL: Permiso custom "{codename}" NO EXISTE. ¿Falta correr migrations?'))

            # Assign and Save
            grupo.permissions.set(perms_to_add)
            self.stdout.write(self.style.SUCCESS(f'Se asignaron {len(perms_to_add)} permisos al grupo "{nombre_grupo}".'))

        self.stdout.write(self.style.SUCCESS('¡Configuración de Roles y Permisos (RBAC) finalizada con éxito!'))
