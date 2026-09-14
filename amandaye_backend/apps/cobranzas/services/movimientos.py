"""Financial writers lock CuentaCorriente -> Pago -> Cargo -> AplicacionPago."""
from decimal import Decimal, DecimalException
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from apps.cobranzas.models import AplicacionPago, Cargo, CuentaCorriente, Pago


def exigir_permiso(usuario, permiso):
    if (not usuario or not usuario.is_authenticated or not usuario.is_active
            or not usuario.has_perm(permiso)):
        raise PermissionDenied("No tiene permiso para realizar esta operación.")


def validar_importe(valor):
    try:
        importe = Decimal(str(valor))
        if (not importe.is_finite() or importe <= 0
                or importe > Decimal('99999999.99')
                or importe != importe.quantize(Decimal('0.01'))):
            raise ValidationError("El importe debe ser positivo y tener como máximo dos decimales.")
        # Normalize harmless trailing zeroes only after exact-cent validation.
        # Multiplying a tariff by Decimal('2.00') produces four decimal places.
        return importe.quantize(Decimal('0.01'))
    except (DecimalException, TypeError, ValueError):
        raise ValidationError("El importe no es válido.") from None


def bloquear_movimientos(cuenta_id, pago_id, cargo_id):
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta_id)
    pago = Pago.objects.select_for_update().get(pk=pago_id)
    cargo = Cargo.objects.select_for_update().get(pk=cargo_id)
    if pago.cuenta_id != cuenta.pk or cargo.cuenta_id != cuenta.pk:
        raise ValidationError("El pago y el cargo deben pertenecer a la misma cuenta.")
    return cuenta, pago, cargo


def totales_actuales(pago, cargo):
    # Locking reads see current rows even under MySQL REPEATABLE READ.
    aplicaciones = list(AplicacionPago.objects.select_for_update().filter(
        Q(pago_id=pago.pk) | Q(cargo_id=cargo.pk), estado=AplicacionPago.Estado.ACTIVA,
    ).order_by('pk'))
    total_pago = sum((a.importe_aplicado for a in aplicaciones if a.pago_id == pago.pk), Decimal('0.00'))
    total_cargo = sum((a.importe_aplicado for a in aplicaciones if a.cargo_id == cargo.pk), Decimal('0.00'))
    if not 0 <= total_pago <= pago.importe_total or not 0 <= total_cargo <= cargo.importe:
        raise ValidationError("Los movimientos requieren conciliación antes de continuar.")
    return total_pago, total_cargo


def guardar_estado_cargo(cargo, total):
    if not 0 <= total <= cargo.importe:
        raise ValidationError("El cargo presenta un saldo inconsistente.")
    cargo.estado = (Cargo.Estado.PAGADO if total == cargo.importe else
                    Cargo.Estado.PARCIAL if total else Cargo.Estado.PENDIENTE)
    cargo.save(update_fields=['estado', 'updated_at'])
