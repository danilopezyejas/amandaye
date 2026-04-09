import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.cobranzas.models import Pago, Cargo, AplicacionPago, CuentaCorriente

def registrar_pago(cuenta: CuentaCorriente, fecha_pago: datetime.date, importe_total: Decimal, medio_pago: str, referencia: str = None, observaciones: str = None) -> Pago:
    if importe_total <= 0:
        raise ValidationError("El importe del pago debe ser mayor a 0.")
        
    pago = Pago.objects.create(
        cuenta=cuenta,
        fecha_pago=fecha_pago,
        importe_total=importe_total,
        medio_pago=medio_pago,
        referencia=referencia,
        observaciones=observaciones
    )
    return pago

@transaction.atomic
def aplicar_pago(pago: Pago, cargo: Cargo, importe_aplicar: Decimal) -> AplicacionPago:
    if importe_aplicar <= 0:
        raise ValidationError("El importe a aplicar debe ser mayor a 0.")
    if pago.cuenta != cargo.cuenta:
        raise ValidationError("El pago y el cargo no pertenecen a la misma cuenta.")
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError("No se puede aplicar a un cargo anulado.")
        
    if importe_aplicar > pago.saldo_disponible:
        raise ValidationError(f"El importe a aplicar supera el saldo disponible del pago ({pago.saldo_disponible}).")
        
    if importe_aplicar > cargo.saldo_pendiente:
        raise ValidationError(f"El importe a aplicar supera el saldo pendiente del cargo ({cargo.saldo_pendiente}).")
        
    aplicacion = AplicacionPago.objects.create(
        pago=pago,
        cargo=cargo,
        importe_aplicado=importe_aplicar
    )
    
    # Recalcular estado del cargo
    if cargo.saldo_pendiente == 0:
        cargo.estado = Cargo.Estado.PAGADO
    else:
        cargo.estado = Cargo.Estado.PARCIAL
    cargo.save()
    
    return aplicacion

@transaction.atomic
def revertir_aplicacion(aplicacion: AplicacionPago, motivo: str = None):
    from django.utils import timezone
    if aplicacion.estado == AplicacionPago.Estado.REVERTIDA:
        from django.core.exceptions import ValidationError
        raise ValidationError("Esta aplicación ya fue revertida.")

    cargo = aplicacion.cargo
    
    # Soft-delete: marcar como revertida sin borrar el registro
    aplicacion.estado = AplicacionPago.Estado.REVERTIDA
    aplicacion.fecha_reversion = timezone.now()
    aplicacion.motivo_reversion = motivo or "Reversión manual"
    aplicacion.save()
    
    # Recalculamos el estado del cargo en base a las aplicaciones ACTIVAS restantes
    if cargo.saldo_pendiente >= cargo.importe:
        cargo.estado = Cargo.Estado.PENDIENTE
    elif cargo.saldo_pendiente > 0:
        cargo.estado = Cargo.Estado.PARCIAL
    else:
        cargo.estado = Cargo.Estado.PAGADO
    cargo.save()
