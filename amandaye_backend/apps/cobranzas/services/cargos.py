import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.cobranzas.models import Cargo, CuentaCorriente, ConceptoCobro

def crear_cargo(cuenta: CuentaCorriente, concepto: ConceptoCobro, periodo: str, fecha_emision: datetime.date, fecha_vencimiento: datetime.date, importe: Decimal, observaciones: str = None) -> Cargo:
    if importe <= 0:
        raise ValidationError("El importe del cargo debe ser mayor a 0.")
        
    cargo = Cargo.objects.create(
        cuenta=cuenta,
        concepto=concepto,
        periodo=periodo,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        importe=importe,
        estado=Cargo.Estado.PENDIENTE,
        observaciones=observaciones
    )
    return cargo

def anular_cargo(cargo: Cargo, observaciones: str = None) -> Cargo:
    if cargo.aplicaciones.exists():
        raise ValidationError("No se puede anular un cargo que ya tiene pagos aplicados. Revierta los pagos primero.")
    
    cargo.estado = Cargo.Estado.ANULADO
    if observaciones:
        cargo.observaciones = (cargo.observaciones or "") + "\nANULADO: " + observaciones
    cargo.save()
    return cargo
