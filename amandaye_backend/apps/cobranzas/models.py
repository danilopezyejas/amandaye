from decimal import Decimal
from django.db import models
from django.db.models import Sum
from apps.usuarios.models import Socios

class CuentaCorriente(models.Model):
    class TipoCuenta(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', 'Individual'
        FAMILIAR = 'FAMILIAR', 'Familiar'

    class Estado(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        CERRADA = 'CERRADA', 'Cerrada'

    socio_titular = models.OneToOneField(
        'usuarios.Socios', 
        on_delete=models.PROTECT, 
        related_name='cuenta_corriente',
        help_text="Una cuenta corriente por titular."
    )
    tipo_cuenta = models.CharField(max_length=20, choices=TipoCuenta.choices)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVA)
    fecha_apertura = models.DateField(auto_now_add=True)
    fecha_cierre = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Cuenta Corriente'
        verbose_name_plural = 'Cuentas Corrientes'

    def __str__(self):
        return f"Cuenta {self.tipo_cuenta} - Socio {self.socio_titular.numero}"

class ConceptoCobro(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(null=True, blank=True)
    importe_por_defecto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Importe", help_text="Precio actual o base")
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Concepto de Cobro'
        verbose_name_plural = 'Conceptos de Cobro'

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

class Cargo(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PARCIAL = 'PARCIAL', 'Parcialmente Pagado'
        PAGADO = 'PAGADO', 'Pagado'
        ANULADO = 'ANULADO', 'Anulado'

    cuenta = models.ForeignKey(CuentaCorriente, on_delete=models.PROTECT, related_name='cargos')
    concepto = models.ForeignKey(ConceptoCobro, on_delete=models.PROTECT)
    periodo = models.CharField(max_length=7, help_text="Formato YYYY-MM")
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        constraints = [
            models.CheckConstraint(check=models.Q(importe__gt=0), name='cargo_importe_gt_0')
        ]

    def __str__(self):
        return f"Cargo {self.id} - {self.concepto.codigo} ({self.periodo})"

    @property
    def total_aplicado(self) -> Decimal:
        return self.aplicaciones.filter(estado='ACTIVA').aggregate(total=Sum('importe_aplicado'))['total'] or Decimal('0.00')

    @property
    def saldo_pendiente(self) -> Decimal:
        if self.estado == self.Estado.ANULADO:
            return Decimal('0.00')
        return self.importe - self.total_aplicado

    @property
    def esta_vencido(self) -> bool:
        from datetime import date
        return self.saldo_pendiente > 0 and self.fecha_vencimiento < date.today()

class Pago(models.Model):
    class MedioPago(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia'
        BROU = 'BROU', 'BROU'
        OTRO = 'OTRO', 'Otro'

    cuenta = models.ForeignKey(CuentaCorriente, on_delete=models.PROTECT, related_name='pagos')
    fecha_pago = models.DateField()
    importe_total = models.DecimalField(max_digits=10, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices)
    referencia = models.CharField(max_length=100, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        constraints = [
            models.CheckConstraint(check=models.Q(importe_total__gt=0), name='pago_importe_gt_0')
        ]

    def __str__(self):
        return f"Pago {self.id} de {self.importe_total} - Cuenta {self.cuenta.id}"

    @property
    def total_aplicado(self) -> Decimal:
        return self.aplicaciones.filter(estado='ACTIVA').aggregate(total=Sum('importe_aplicado'))['total'] or Decimal('0.00')

    @property
    def saldo_disponible(self) -> Decimal:
        return self.importe_total - self.total_aplicado

class AplicacionPago(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        REVERTIDA = 'REVERTIDA', 'Revertida'

    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='aplicaciones')
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name='aplicaciones')
    importe_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVA, verbose_name='Estado')
    fecha_reversion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de reversión')
    motivo_reversion = models.TextField(null=True, blank=True, verbose_name='Motivo de reversión')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Aplicación de Pago'
        verbose_name_plural = 'Aplicaciones de Pagos'
        constraints = [
            models.CheckConstraint(check=models.Q(importe_aplicado__gt=0), name='aplicacion_importe_gt_0')
        ]

    def __str__(self):
        return f"Aplicación {self.id}: {self.importe_aplicado} al Cargo {self.cargo.id} [{self.estado}]"
