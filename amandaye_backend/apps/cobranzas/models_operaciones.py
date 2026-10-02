"""Additive records for financial retries, explicit credit intent and receipts."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class IntencionSaldo(models.TextChoices):
    ANTICIPO = 'ANTICIPO', 'Anticipo intencional'
    APLICAR = 'APLICAR', 'Pendiente de aplicación'
    SIN_CLASIFICAR = 'SIN_CLASIFICAR', 'Sin clasificar'


class OperacionCobro(models.Model):
    class Tipo(models.TextChoices):
        COBRO = 'COBRO', 'Nuevo cobro'
        APLICACION = 'APLICACION', 'Aplicación de saldo existente'

    clave = models.UUIDField(unique=True, editable=False)
    huella = models.CharField(max_length=64, editable=False)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    cuenta = models.ForeignKey('cobranzas.CuentaCorriente', on_delete=models.PROTECT)
    pago = models.ForeignKey('cobranzas.Pago', on_delete=models.PROTECT, related_name='operaciones')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    intencion_anterior = models.CharField(max_length=16, choices=IntencionSaldo.choices)
    intencion_saldo = models.CharField(max_length=16, choices=IntencionSaldo.choices)
    aplicaciones = models.JSONField(default=list, editable=False)
    saldo_final = models.DecimalField(max_digits=10, decimal_places=2)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class IntencionSaldoPago(models.Model):
    pago = models.OneToOneField('cobranzas.Pago', on_delete=models.PROTECT, related_name='intencion_saldo')
    intencion = models.CharField(max_length=16, choices=IntencionSaldo.choices)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actualizado_en = models.DateTimeField(auto_now=True)


class ComprobantePago(models.Model):
    pago = models.OneToOneField('cobranzas.Pago', on_delete=models.PROTECT, related_name='comprobante')
    numero = models.CharField(max_length=32, unique=True, editable=False)
    datos = models.JSONField(editable=False)
    reconstruido = models.BooleanField(default=False, editable=False)
    emitido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    emitido_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Los datos originales del comprobante son inmutables.')
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ['-pk']
