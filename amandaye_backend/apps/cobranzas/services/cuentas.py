from decimal import Decimal
from django.db import transaction
from apps.cobranzas.models import CuentaCorriente
from apps.usuarios.models import Socios

def crear_cuenta_corriente_para_titular(socio: Socios) -> CuentaCorriente:
    """Crea o retorna la cuenta corriente activa de un socio titular."""
    cuenta = CuentaCorriente.objects.filter(socio_titular=socio).first()
    if cuenta:
        if cuenta.estado == CuentaCorriente.Estado.CERRADA:
            cuenta.estado = CuentaCorriente.Estado.ACTIVA
            cuenta.fecha_cierre = None
            cuenta.save()
        return cuenta
    
    # Determinar tipo
    tipo_cuenta = (
        CuentaCorriente.TipoCuenta.FAMILIAR 
        if socio.tipo and 'familiar' in socio.tipo.lower()
        else CuentaCorriente.TipoCuenta.INDIVIDUAL
    )
    
    cuenta = CuentaCorriente.objects.create(
        socio_titular=socio,
        tipo_cuenta=tipo_cuenta,
        estado=CuentaCorriente.Estado.ACTIVA
    )
    return cuenta

def obtener_estado_cuenta(cuenta: CuentaCorriente) -> dict:
    """Obtiene el estado completo de la cuenta."""
    cargos = cuenta.cargos.all().order_by('-fecha_emision')
    pagos = cuenta.pagos.all().order_by('-fecha_pago')
    
    saldo_total = sum((c.saldo_pendiente for c in cargos if c.estado != 'ANULADO'), Decimal('0.00'))
    deuda_vencida = sum((c.saldo_pendiente for c in cargos if c.esta_vencido), Decimal('0.00'))
    
    # Resumen por estado
    resumen = {}
    for c in cargos:
        if c.estado not in resumen:
            resumen[c.estado] = 0
        resumen[c.estado] += 1

    # Estado general de la cuenta
    if saldo_total <= 0:
        estado_cuenta = 'AL_DIA'
    elif cuenta.estado == CuentaCorriente.Estado.CERRADA:
        estado_cuenta = 'MOROSO'
    else:
        estado_cuenta = 'CON_DEUDA'
        
    return {
        'titular': cuenta.socio_titular.numero,
        'tipo': cuenta.tipo_cuenta,
        'saldo_total': saldo_total,
        'deuda_vencida': deuda_vencida,
        'resumen_estados': resumen,
        'estado_cuenta': estado_cuenta,
        'cargos': cargos,
        'pagos': pagos
    }
