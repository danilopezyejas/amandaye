from django.core.management.base import BaseCommand
from apps.usuarios.services.habilitacion import recalcular_habilitados

class Command(BaseCommand):
    help = 'Recalcula el estado de habilitacion de las personas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--socio',
            type=int,
            help='Número de socio para recalcular solo sus personas asociadas',
        )

    def handle(self, *args, **options):
        socio_id = options.get('socio')
        
        if socio_id:
            self.stdout.write(self.style.NOTICE(f'Iniciando recálculo para el socio {socio_id}...'))
        else:
            self.stdout.write(self.style.NOTICE('Iniciando recálculo masivo de habilitaciones...'))
            
        resultados = recalcular_habilitados(socio_id)
        
        self.stdout.write(self.style.SUCCESS('Recálculo finalizado.'))
        self.stdout.write(f"Evaluados: {resultados['evaluados']}")
        self.stdout.write(self.style.SUCCESS(f"Habilitados: {resultados['habilitados']}"))
        self.stdout.write(self.style.WARNING(f"Suspendidos: {resultados['suspendidos']}"))
        self.stdout.write(self.style.ERROR(f"Revocados: {resultados['revocados']}"))
        self.stdout.write(f"No Habilitados: {resultados['no_habilitados']}")
