import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.cobranzas.models import AplicacionPago, Cargo, CuentaCorriente, Pago
from apps.cobranzas.services.movimientos import (
    bloquear_movimientos, exigir_permiso, guardar_estado_cargo,
    totales_actuales, validar_importe,
)


@transaction.atomic
def registrar_pago(cuenta: CuentaCorriente, fecha_pago: datetime.date, importe_total: Decimal,
                   medio_pago: str, referencia=None, observaciones=None, usuario=None) -> Pago:
    exigir_permiso(usuario, 'cobranzas.add_pago')
    importe_total = validar_importe(importe_total)
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta.pk)
    # Closed accounts still accept settlement of historical debt.
    pago = Pago(cuenta=cuenta, fecha_pago=fecha_pago, importe_total=importe_total,
                medio_pago=medio_pago, referencia=referencia,
                observaciones=observaciones, registrado_por=usuario)
    pago.full_clean()
    pago.save()
    return pago


@transaction.atomic
def aplicar_pago(pago: Pago, cargo: Cargo, importe_aplicar: Decimal, usuario=None) -> AplicacionPago:
    exigir_permiso(usuario, 'cobranzas.puede_aplicar_pago')
    importe = validar_importe(importe_aplicar)
    cuenta, pago, cargo = bloquear_movimientos(pago.cuenta_id, pago.pk, cargo.pk)
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError('No se puede aplicar a un cargo anulado.')
    total_pago, total_cargo = totales_actuales(pago, cargo)
    if importe > pago.importe_total - total_pago:
        raise ValidationError('Saldo disponible del pago insuficiente.')
    if importe > cargo.importe - total_cargo:
        raise ValidationError('El importe supera el saldo pendiente del cargo.')
    aplicacion = AplicacionPago.objects.create(
        pago=pago, cargo=cargo, importe_aplicado=importe, registrado_por=usuario,
    )
    guardar_estado_cargo(cargo, total_cargo + importe)
    from apps.usuarios.services.habilitacion import recalcular_habilitados
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)
    return aplicacion


@transaction.atomic
def revertir_aplicacion(aplicacion: AplicacionPago, motivo=None, usuario=None):
    exigir_permiso(usuario, 'cobranzas.puede_revertir_aplicacion_pago')
    origen = AplicacionPago.objects.only('pago_id', 'cargo_id').get(pk=aplicacion.pk)
    cuenta_id = Pago.objects.values_list('cuenta_id', flat=True).get(pk=origen.pago_id)
    cuenta, pago, cargo = bloquear_movimientos(cuenta_id, origen.pago_id, origen.cargo_id)
    aplicacion = AplicacionPago.objects.select_for_update().get(pk=origen.pk)
    if aplicacion.pago_id != pago.pk or aplicacion.cargo_id != cargo.pk:
        raise ValidationError('El movimiento cambió; vuelva a cargarlo.')
    if aplicacion.estado != AplicacionPago.Estado.ACTIVA:
        raise ValidationError('Esta aplicación ya fue revertida.')
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError('El cargo requiere conciliación antes de revertir.')
    _, total_cargo = totales_actuales(pago, cargo)
    aplicacion.estado = AplicacionPago.Estado.REVERTIDA
    aplicacion.fecha_reversion = timezone.now()
    aplicacion.motivo_reversion = motivo or 'Reversión manual'
    aplicacion.revertido_por = usuario
    aplicacion.save(update_fields=[
        'estado', 'fecha_reversion', 'motivo_reversion', 'revertido_por', 'updated_at',
    ])
    guardar_estado_cargo(cargo, total_cargo - aplicacion.importe_aplicado)
    from apps.usuarios.services.habilitacion import recalcular_habilitados
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)
    return aplicacion
