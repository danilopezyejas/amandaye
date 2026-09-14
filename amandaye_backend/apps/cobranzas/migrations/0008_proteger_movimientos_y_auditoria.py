from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cobranzas', '0007_aplicacionpago_registrado_por_pago_registrado_por'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aplicacionpago', name='pago',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='aplicaciones', to='cobranzas.pago'),
        ),
        migrations.AddField(
            model_name='cargo', name='registrado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cargos_registrados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cargo', name='anulado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cargos_anulados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name='cargo', name='fecha_anulacion', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='aplicacionpago', name='revertido_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aplicaciones_revertidas', to=settings.AUTH_USER_MODEL),
        ),
    ]
