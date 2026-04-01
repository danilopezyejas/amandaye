from django.core.management.base import BaseCommand
from apps.cobranzas.services.cuotas import generar_cuotas_mensuales

class Command(BaseCommand):
    help = 'Genera cuotas mensuales para todas las cuentas activas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--periodo', 
            type=str, 
            required=True, 
            help='Periodo en formato YYYY-MM'
        )

    def handle(self, *args, **options):
        periodo = options['periodo']
        self.stdout.write(self.style.WARNING(f"Iniciando generacion de cuotas para el periodo: {periodo}"))
        
        resultados = generar_cuotas_mensuales(periodo)
        
        if "error" in resultados:
            self.stdout.write(self.style.ERROR(resultados["error"]))
            return

        self.stdout.write(self.style.SUCCESS('Generacion completada:'))
        self.stdout.write(f"- Cuentas procesadas: {resultados['cuentas_procesadas']}")
        self.stdout.write(f"- Cuotas nuevas creadas: {resultados['cuotas_creadas']}")
        self.stdout.write(f"- Cuotas omitidas (ya existian): {resultados['cuotas_omitidas']}")
        
        if resultados.get("errores"):
            self.stdout.write(self.style.ERROR(f"Errores encontrados ({len(resultados['errores'])}):"))
            for e in resultados['errores']:
                self.stdout.write(self.style.ERROR(f"  {e}"))
