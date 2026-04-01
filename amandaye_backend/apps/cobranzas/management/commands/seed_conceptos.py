from django.core.management.base import BaseCommand
from apps.cobranzas.models import ConceptoCobro

class Command(BaseCommand):
    help = 'Carga los conceptos de cobro por defecto'

    def handle(self, *args, **options):
        conceptos = [
            {'codigo': 'MATRICULA', 'nombre': 'Matricula de Ingreso', 'descripcion': 'Cobro inicial o de reafiliacion'},
            {'codigo': 'CUOTA_INDIVIDUAL', 'nombre': 'Cuota Individual', 'descripcion': 'Cuota social mensual individual'},
            {'codigo': 'CUOTA_FAMILIAR', 'nombre': 'Cuota Familiar', 'descripcion': 'Cuota social mensual grupo familiar'},
            {'codigo': 'CUOTA_TEMPORADA', 'nombre': 'Cuota de Temporada', 'descripcion': 'Cuota para socio de temporada'},
            {'codigo': 'ADICIONAL_MENOR', 'nombre': 'Adicional Menor', 'descripcion': 'Adicional nuclear extra'},
            {'codigo': 'PERCHA_SIMPLE', 'nombre': 'Percha Simple', 'descripcion': 'Alquiler de percha simple'},
            {'codigo': 'PERCHA_DOBLE', 'nombre': 'Percha Doble', 'descripcion': 'Alquiler de percha doble'},
            {'codigo': 'GUARDERIA', 'nombre': 'Guarderia', 'descripcion': 'Guarderia náutica'},
            {'codigo': 'RECARGO', 'nombre': 'Recargo Comercial', 'descripcion': 'Intereses de mora o recargos'},
            {'codigo': 'DESCUENTO', 'nombre': 'Descuento General', 'descripcion': 'Descuento o bonificacion'},
            {'codigo': 'AJUSTE', 'nombre': 'Ajuste de Cuenta', 'descripcion': 'Ajuste positivo o negativo por diferencias'}
        ]
        
        for c in conceptos:
            obj, created = ConceptoCobro.objects.get_or_create(codigo=c['codigo'], defaults=c)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Creado: {c['codigo']}"))
            else:
                self.stdout.write(f"Ya existia: {c['codigo']}")
