"""Stable internal receipts for collection operations."""
from io import BytesIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.cobranzas.models import ComprobantePago, Pago


def _can_read(user):
    if not user or not user.is_authenticated or not user.is_active or not user.has_perm('cobranzas.view_pago'):
        raise PermissionDenied('No tiene permiso para consultar comprobantes.')


def _snapshot(pago, reconstruido, user):
    aplicaciones = list(pago.aplicaciones.filter(estado='ACTIVA').select_related('cargo__concepto').order_by('pk'))
    return {
        'club': getattr(settings, 'CLUB_NAME', 'Club Amandayé Ipeguá'),
        'moneda': getattr(settings, 'CLUB_CURRENCY', 'UYU'),
        'detalles': getattr(settings, 'CLUB_RECEIPT_DETAILS', ''),
        'pago_id': pago.pk, 'cuenta_id': pago.cuenta_id,
        'socio_numero': pago.cuenta.socio_titular_id,
        'fecha_pago': pago.fecha_pago.isoformat(), 'importe_total': str(pago.importe_total),
        'medio_pago': pago.medio_pago, 'referencia': pago.referencia or '',
        'aplicaciones': [
            {'id': item.pk, 'cargo_id': item.cargo_id, 'concepto': item.cargo.concepto.nombre,
             'periodo': item.cargo.periodo, 'importe': str(item.importe_aplicado)}
            for item in aplicaciones
        ],
        'reconstruido': reconstruido,
        'reconstruido_en': timezone.localtime().isoformat() if reconstruido else None,
        'actor_id': user.pk if user else None,
    }


@transaction.atomic
def reconstruir_comprobante(pago, *, usuario):
    _can_read(usuario)
    pago = Pago.objects.select_for_update().select_related('cuenta__socio_titular').get(pk=pago.pk)
    existing = ComprobantePago.objects.filter(pago=pago).first()
    if existing:
        return existing
    numero = f'RC-{pago.pk:08d}'
    return emitir_comprobante(pago, usuario=usuario, reconstruido=True)


@transaction.atomic
def emitir_comprobante(pago, *, usuario, reconstruido=False):
    _can_read(usuario)
    pago = Pago.objects.select_for_update().select_related('cuenta__socio_titular').get(pk=pago.pk)
    existing = ComprobantePago.objects.filter(pago=pago).first()
    if existing:
        return existing
    return ComprobantePago.objects.create(
        pago=pago, numero=f'RC-{pago.pk:08d}',
        datos=_snapshot(pago, reconstruido, usuario),
        reconstruido=reconstruido, emitido_por=usuario,
    )


def obtener_comprobante(pago, *, usuario):
    _can_read(usuario)
    return ComprobantePago.objects.get(pago=pago)


def generar_pdf(comprobante, *, usuario):
    _can_read(usuario)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    datos = comprobante.datos
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setTitle(f'Comprobante {comprobante.numero}')
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(50, y, datos['club'])
    y -= 26
    pdf.setFont('Helvetica', 10)
    pdf.drawString(50, y, f"Comprobante interno {comprobante.numero}")
    y -= 18
    if datos.get('reconstruido'):
        pdf.drawString(50, y, 'Reconstruido a partir del pago registrado')
        y -= 18
    for line in (
        f"Socio: {datos['socio_numero']}", f"Fecha: {datos['fecha_pago']}",
        f"Medio: {datos['medio_pago']}", f"Referencia: {datos['referencia'] or '—'}",
        f"Importe: {datos['moneda']} {datos['importe_total']}",
    ):
        pdf.drawString(50, y, line)
        y -= 16
    y -= 8
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(50, y, 'Aplicaciones')
    y -= 16
    pdf.setFont('Helvetica', 9)
    for row in datos['aplicaciones']:
        pdf.drawString(50, y, f"Cargo {row['cargo_id']} · {row['concepto']} · {row['periodo']} · {datos['moneda']} {row['importe']}")
        y -= 14
        if y < 60:
            pdf.showPage()
            y = height - 60
    if datos.get('detalles'):
        y -= 10
        pdf.drawString(50, y, datos['detalles'][:160])
    pdf.save()
    return output.getvalue()
