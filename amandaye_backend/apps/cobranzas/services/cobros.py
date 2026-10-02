"""Atomic daily collection workflow used by the internal management panel."""
import datetime
import hashlib
import json
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cobranzas.models import (
    AplicacionPago, Cargo, CuentaCorriente, IntencionSaldo, IntencionSaldoPago,
    OperacionCobro, Pago,
)
from apps.cobranzas.services.movimientos import exigir_permiso, validar_importe
from apps.cobranzas.services.pagos import aplicar_pago, registrar_pago

MAX_APPLICATIONS = 100


def _require_user(user, permission):
    exigir_permiso(user, permission)


def _fingerprint(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _application_payload(applications):
    rows = []
    for item in applications or []:
        try:
            cargo_id = int(item['cargo_id'])
            amount = validar_importe(item['importe'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError('Cada aplicación debe indicar cargo_id e importe válido.') from exc
        rows.append({'cargo_id': cargo_id, 'importe': str(amount)})
    if len(rows) > MAX_APPLICATIONS:
        raise ValidationError(f'No se pueden aplicar más de {MAX_APPLICATIONS} cargos en una operación.')
    if len({row['cargo_id'] for row in rows}) != len(rows):
        raise ValidationError('Un cargo no puede repetirse en la misma operación.')
    return sorted(rows, key=lambda row: row['cargo_id'])


def _validate_intention(value, remaining):
    valid = {choice for choice, _ in IntencionSaldo.choices}
    if value not in valid:
        raise ValidationError('La intención del saldo no es válida.')
    if remaining > 0 and value == IntencionSaldo.SIN_CLASIFICAR:
        raise ValidationError('Clasifique el saldo restante como anticipo o pendiente de aplicación.')
    return value


def _current_proposal(cuenta, importe, *, payment=None):
    queryset = Cargo.objects.filter(
        cuenta=cuenta,
        estado__in=(Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL),
    ).select_related('concepto').prefetch_related('aplicaciones').order_by(
        'fecha_vencimiento', 'fecha_emision', 'pk',
    )
    remaining = validar_importe(importe)
    rows = []
    for cargo in queryset:
        saldo = cargo.saldo_pendiente
        if saldo <= 0:
            continue
        applied = min(remaining, saldo)
        rows.append({
            'cargo_id': cargo.pk,
            'concepto': cargo.concepto.nombre,
            'periodo': cargo.periodo,
            'fecha_vencimiento': cargo.fecha_vencimiento.isoformat(),
            'saldo': str(saldo),
            'importe': str(applied),
        })
        remaining -= applied
        if remaining <= 0:
            break
    version = _fingerprint({
        'cuenta': cuenta.pk,
        'pago': payment.pk if payment else None,
        'importe': str(validar_importe(importe)),
        'cargos': [(row['cargo_id'], row['saldo']) for row in rows],
    })
    return rows, version, remaining


def proponer_aplicaciones(cuenta, importe, pago=None, *, usuario):
    _require_user(usuario, 'cobranzas.view_cuentacorriente')
    if pago is not None:
        if pago.cuenta_id != cuenta.pk:
            raise ValidationError('El pago y la cuenta no coinciden.')
        importe = pago.saldo_disponible
    rows, version, remaining = _current_proposal(cuenta, importe, payment=pago)
    return {
        'filas': rows,
        'version': version,
        'saldo_sin_aplicar': remaining,
    }


def _check_operation_key(clave, huella):
    if not isinstance(clave, UUID):
        try:
            clave = UUID(str(clave))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError('La clave de operación no es válida.') from exc
    existing = OperacionCobro.objects.filter(clave=clave).select_related('pago').first()
    if existing:
        if existing.huella != huella:
            raise ValidationError('La clave ya fue utilizada con otros datos.')
        return existing
    return None


def _save_intention(pago, intention, user):
    record, _ = IntencionSaldoPago.objects.select_for_update().get_or_create(
        pago=pago,
        defaults={'intencion': intention, 'actualizado_por': user},
    )
    if record.intencion != intention:
        record.intencion = intention
        record.actualizado_por = user
        record.save(update_fields=['intencion', 'actualizado_por', 'actualizado_en'])
    return record


def _snapshot(applications):
    return [
        {'cargo_id': application.cargo_id, 'importe': str(application.importe_aplicado)}
        for application in applications
    ]


@transaction.atomic
def confirmar_cobro(*, cuenta, usuario, clave, fecha_pago, importe_total, medio_pago,
                    referencia='', aplicaciones=None, intencion_saldo=IntencionSaldo.SIN_CLASIFICAR,
                    version=None):
    _require_user(usuario, 'cobranzas.add_pago')
    rows = _application_payload(aplicaciones)
    importe_total = validar_importe(importe_total)
    if not isinstance(fecha_pago, datetime.date):
        raise ValidationError('La fecha de pago no es válida.')
    payload = {
        'tipo': 'COBRO', 'cuenta': cuenta.pk, 'fecha_pago': fecha_pago.isoformat(),
        'importe_total': str(importe_total), 'medio_pago': medio_pago,
        'referencia': referencia or '', 'aplicaciones': rows,
        'intencion_saldo': intencion_saldo, 'version': version,
    }
    huella = _fingerprint(payload)
    existing = _check_operation_key(clave, huella)
    if existing:
        return existing

    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta.pk)
    existing = _check_operation_key(clave, huella)
    if existing:
        return existing
    proposed, current_version, _ = _current_proposal(cuenta, importe_total)
    if version is not None and version != current_version:
        raise ValidationError('La propuesta cambió; vuelva a revisar las aplicaciones.')
    proposed_by_id = {row['cargo_id']: row for row in proposed}
    for row in rows:
        if row['cargo_id'] not in proposed_by_id:
            raise ValidationError('Una aplicación no pertenece a un cargo pendiente de esta cuenta.')
        if Decimal(row['importe']) > Decimal(proposed_by_id[row['cargo_id']]['saldo']):
            raise ValidationError('Una aplicación supera el saldo actual del cargo.')
    total_applied = sum((Decimal(row['importe']) for row in rows), Decimal('0.00'))
    remaining = importe_total - total_applied
    _validate_intention(intencion_saldo, remaining)

    pago = registrar_pago(
        cuenta, fecha_pago, importe_total, medio_pago,
        referencia=referencia or None, usuario=usuario,
    )
    saved_applications = []
    for row in rows:
        cargo = Cargo.objects.get(pk=row['cargo_id'])
        saved_applications.append(aplicar_pago(pago, cargo, Decimal(row['importe']), usuario=usuario))
    _save_intention(pago, intencion_saldo if remaining > 0 else IntencionSaldo.SIN_CLASIFICAR, usuario)
    operation = OperacionCobro.objects.create(
        clave=UUID(str(clave)), huella=huella, tipo=OperacionCobro.Tipo.COBRO,
        cuenta=cuenta, pago=pago, usuario=usuario,
        intencion_anterior=IntencionSaldo.SIN_CLASIFICAR,
        intencion_saldo=intencion_saldo if remaining > 0 else IntencionSaldo.SIN_CLASIFICAR,
        aplicaciones=_snapshot(saved_applications), saldo_final=pago.saldo_disponible,
    )
    from apps.cobranzas.services.comprobantes import emitir_comprobante
    emitir_comprobante(pago, usuario=usuario)
    return operation


@transaction.atomic
def aplicar_saldo(*, pago, usuario, clave, aplicaciones=None,
                  intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=None):
    _require_user(usuario, 'cobranzas.puede_aplicar_pago')
    rows = _application_payload(aplicaciones)
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=pago.cuenta_id)
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    remaining_before = pago.saldo_disponible
    payload = {
        'tipo': 'APLICACION', 'cuenta': cuenta.pk, 'pago': pago.pk,
        'aplicaciones': rows, 'intencion_saldo': intencion_saldo, 'version': version,
    }
    huella = _fingerprint(payload)
    existing = _check_operation_key(clave, huella)
    if existing:
        return existing
    proposed, current_version, _ = _current_proposal(cuenta, remaining_before, payment=pago)
    if version is not None and version != current_version:
        raise ValidationError('La propuesta cambió; vuelva a revisar las aplicaciones.')
    proposed_by_id = {row['cargo_id']: row for row in proposed}
    for row in rows:
        if row['cargo_id'] not in proposed_by_id:
            raise ValidationError('Una aplicación no pertenece a un cargo pendiente de esta cuenta.')
        if Decimal(row['importe']) > Decimal(proposed_by_id[row['cargo_id']]['saldo']):
            raise ValidationError('Una aplicación supera el saldo actual del cargo.')
    total_applied = sum((Decimal(row['importe']) for row in rows), Decimal('0.00'))
    remaining = remaining_before - total_applied
    if total_applied > remaining_before:
        raise ValidationError('La aplicación supera el saldo disponible del pago.')
    current_intention = getattr(getattr(pago, 'intencion_saldo', None), 'intencion', IntencionSaldo.SIN_CLASIFICAR)
    _validate_intention(intencion_saldo, remaining)
    saved_applications = []
    for row in rows:
        cargo = Cargo.objects.get(pk=row['cargo_id'])
        saved_applications.append(aplicar_pago(pago, cargo, Decimal(row['importe']), usuario=usuario))
    final_intention = intencion_saldo if remaining > 0 else IntencionSaldo.SIN_CLASIFICAR
    _save_intention(pago, final_intention, usuario)
    operation = OperacionCobro.objects.create(
        clave=UUID(str(clave)), huella=huella, tipo=OperacionCobro.Tipo.APLICACION,
        cuenta=cuenta, pago=pago, usuario=usuario,
        intencion_anterior=current_intention, intencion_saldo=final_intention,
        aplicaciones=_snapshot(saved_applications), saldo_final=pago.saldo_disponible,
    )
    from apps.cobranzas.services.comprobantes import emitir_comprobante
    emitir_comprobante(pago, usuario=usuario)
    return operation
