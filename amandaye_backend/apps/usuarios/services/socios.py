import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.usuarios.models import Socios, Personas, Socios_cambios
from apps.cobranzas.services.cuentas import crear_cuenta_corriente_para_titular
from apps.cobranzas.services.cargos import crear_cargo
from apps.cobranzas.models import ConceptoCobro, CuentaCorriente


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def obtener_siguiente_numero_socio() -> int:
    ultimo = Socios.objects.order_by('-numero').first()
    return ultimo.numero + 1 if ultimo else 1000


def _siguiente_id_cambios() -> int:
    ultimo = Socios_cambios.objects.order_by('-id').first()
    return ultimo.id + 1 if ultimo else 1


def _registrar_cambio(accion: str, comentario: str):
    """Registra en socios_cambios. El campo accion debe estar en SET('Alta','Baja','Rechazo')."""
    Socios_cambios.objects.create(
        id=_siguiente_id_cambios(),
        fecha=datetime.date.today(),
        accion=accion,
        comentario=comentario,
    )


def _calcular_edad(fecha_nacimiento: datetime.date) -> int:
    hoy = datetime.date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


def _validar_titular(datos: dict):
    """Valida campos obligatorios y edad del titular (>=18)."""
    campos = ['Cedula', 'PrimerNombre', 'PrimerApellido', 'FechaNacimiento', 'Telefono', 'Direccion']
    for campo in campos:
        if not datos.get(campo):
            raise ValidationError(f"El campo '{campo}' es obligatorio para el titular.")

    fecha_nac = datos['FechaNacimiento']
    if isinstance(fecha_nac, str):
        try:
            fecha_nac = datetime.date.fromisoformat(fecha_nac)
        except ValueError:
            raise ValidationError("FechaNacimiento del titular debe tener formato YYYY-MM-DD.")

    if _calcular_edad(fecha_nac) < 18:
        raise ValidationError("El titular debe ser mayor de edad (18 años o más).")


def _validar_familiar(datos: dict, relacion: str):
    """Valida campos obligatorios y edad del integrante familiar."""
    campos = ['Cedula', 'PrimerNombre', 'PrimerApellido', 'FechaNacimiento']
    for campo in campos:
        if not datos.get(campo):
            raise ValidationError(f"El campo '{campo}' es obligatorio para el familiar ({relacion}).")

    fecha_nac = datos.get('FechaNacimiento')
    if isinstance(fecha_nac, str):
        try:
            fecha_nac = datetime.date.fromisoformat(fecha_nac)
        except ValueError:
            raise ValidationError("FechaNacimiento del familiar debe tener formato YYYY-MM-DD.")

    edad = _calcular_edad(fecha_nac)
    rel = relacion.upper()

    if rel in ['PAREJA', 'ESPOSO', 'ESPOSA', 'TUTOR'] and edad < 18:
        raise ValidationError(f"La pareja/tutor debe ser mayor de edad (18 años o más). Edad detectada: {edad}.")
    if rel == 'HIJO' and edad >= 18:
        raise ValidationError(f"Los hijos deben ser menores de 18 años. Edad detectada: {edad}.")


def _obtener_concepto(codigo: str) -> ConceptoCobro:
    """Obtiene un ConceptoCobro y valida que tenga importe_por_defecto > 0."""
    try:
        concepto = ConceptoCobro.objects.get(codigo=codigo)
    except ConceptoCobro.DoesNotExist:
        raise ValidationError(f"No existe un Concepto de Cobro con código '{codigo}'. Configúrelo en el panel de Cobranzas.")
    if concepto.importe_por_defecto <= 0:
        raise ValidationError(f"El concepto '{codigo}' tiene importe_por_defecto en $0. Defina un importe válido antes de aprobar socios.")
    return concepto


# ---------------------------------------------------------------------------
# Servicio: Crear solicitud
# ---------------------------------------------------------------------------

@transaction.atomic
def crear_solicitud_socio(datos_titular: dict, datos_familiares: list = None) -> Socios:
    """
    Crea la solicitud de un socio nuevo en estado PENDIENTE.
    - Completa fechaSolicitud
    - NO asigna fechaAlta (se asigna al aprobar)
    - Valida campos obligatorios y edades
    """
    _validar_titular(datos_titular)

    if Personas.objects.filter(Cedula=datos_titular["Cedula"]).exists():
        raise ValidationError("Ya existe una persona con esta cédula.")

    if datos_familiares and len(datos_familiares) > 3:
        raise ValidationError("El núcleo familiar no puede exceder 3 integrantes adicionales (pareja + 2 hijos).")

    # Validar composición del núcleo familiar
    parejas = 0
    hijos = 0
    if datos_familiares:
        for f in datos_familiares:
            relacion = f.get("relacionTitular", "").upper()
            _validar_familiar(f, relacion)
            if relacion in ["PAREJA", "ESPOSO", "ESPOSA", "TUTOR"]:
                parejas += 1
            elif relacion == "HIJO":
                hijos += 1
            if parejas > 1:
                raise ValidationError("Solo se permite 1 pareja/tutor en el núcleo familiar.")
            if hijos > 2:
                raise ValidationError("Solo se permiten hasta 2 hijos en el núcleo familiar.")

    numero_socio = obtener_siguiente_numero_socio()

    # Crear persona titular
    Personas.objects.create(
        Cedula=datos_titular["Cedula"],
        numeroSocio=numero_socio,
        PrimerNombre=datos_titular.get("PrimerNombre", ""),
        SegundoNombre=datos_titular.get("SegundoNombre", ""),
        PrimerApellido=datos_titular.get("PrimerApellido", ""),
        SegundoApellido=datos_titular.get("SegundoApellido", ""),
        FechaNacimiento=datos_titular.get("FechaNacimiento"),
        Direccion=datos_titular.get("Direccion", ""),
        Telefono=datos_titular.get("Telefono", ""),
        relacionTitular="TITULAR",
    )

    # Crear familiares
    tipo_socio = "FAMILIAR" if datos_familiares else "INDIVIDUAL"
    if datos_familiares:
        for f in datos_familiares:
            relacion = f.get("relacionTitular", "").upper()
            Personas.objects.create(
                Cedula=f.get("Cedula"),
                numeroSocio=numero_socio,
                PrimerNombre=f.get("PrimerNombre", ""),
                SegundoNombre=f.get("SegundoNombre", ""),
                PrimerApellido=f.get("PrimerApellido", ""),
                SegundoApellido=f.get("SegundoApellido", ""),
                FechaNacimiento=f.get("FechaNacimiento"),
                relacionTitular=relacion,
            )

    socio = Socios.objects.create(
        numero=numero_socio,
        activo=2,  # PENDIENTE
        fechaSolicitud=datetime.date.today(),
        fechaAlta=None,  # Se asignará al aprobar
        tipo=tipo_socio,
        cedulaTitular=datos_titular["Cedula"],
    )

    _registrar_cambio("Alta", f"[SOLICITUD INGRESO] Socio {numero_socio} registrado en estado PENDIENTE.")
    return socio


# ---------------------------------------------------------------------------
# Servicio: Aprobar socio
# ---------------------------------------------------------------------------

@transaction.atomic
def aprobar_socio(socio: Socios, generar_cargos_iniciales: bool = True) -> Socios:
    """
    Aprueba un socio PENDIENTE: pasa a ALTA, crea CuentaCorriente y emite cargos iniciales.
    - Bloquea si tiene deuda histórica pendiente
    - Matrícula doble si reingresa en menos de 1 año
    - Importes siempre desde ConceptoCobro.importe_por_defecto
    """
    if socio.esta_rechazado:
        raise ValidationError("No se puede aprobar un socio RECHAZADO. Cree una nueva solicitud.")
    if not socio.esta_pendiente:
        if socio.esta_activo:
            raise ValidationError("El socio ya está en estado ALTA.")
        raise ValidationError("El socio no está PENDIENTE.")

    # Validar deuda histórica
    cuenta_historica = CuentaCorriente.objects.filter(socio_titular=socio).first()
    if cuenta_historica:
        from apps.cobranzas.services.cuentas import obtener_estado_cuenta
        estado_cc = obtener_estado_cuenta(cuenta_historica)
        if estado_cc['saldo_total'] > 0:
            raise ValidationError(
                f"El socio arrastra una deuda pendiente de ${estado_cc['saldo_total']}. "
                f"Debe abonar su saldo histórico antes de reafiliarse."
            )

    socio.activo = 1
    socio.fechaAprobacion = datetime.date.today()
    socio.fechaAlta = datetime.date.today()
    socio.save()

    # Crear o reactivar CuentaCorriente
    cuenta = crear_cuenta_corriente_para_titular(socio)

    if generar_cargos_iniciales:
        from decimal import Decimal
        periodo = datetime.date.today().strftime('%Y-%m')
        hoy = datetime.date.today()
        vence = hoy + datetime.timedelta(days=10)

        # --- Matrícula ---
        concepto_mat = _obtener_concepto("MATRICULA")
        precio_mat = concepto_mat.importe_por_defecto

        # Matrícula doble por reingreso dentro del año
        if socio.fechaBaja:
            delta = socio.fechaAlta - socio.fechaBaja
            if delta.days <= 365:
                precio_mat = precio_mat * Decimal('2.00')

        crear_cargo(
            cuenta=cuenta,
            concepto=concepto_mat,
            periodo=periodo,
            fecha_emision=hoy,
            fecha_vencimiento=vence,
            importe=precio_mat,
            observaciones="Matrícula automática de alta / reingreso",
        )

        # --- Primera cuota mensual ---
        codigo_cuota = (
            "CUOTA_FAMILIAR"
            if socio.tipo and 'familiar' in socio.tipo.lower()
            else "CUOTA_INDIVIDUAL"
        )
        concepto_cuota = _obtener_concepto(codigo_cuota)
        crear_cargo(
            cuenta=cuenta,
            concepto=concepto_cuota,
            periodo=periodo,
            fecha_emision=hoy,
            fecha_vencimiento=vence,
            importe=concepto_cuota.importe_por_defecto,
            observaciones=f"Cuota mensual inicial ({socio.tipo})",
        )

    _registrar_cambio(
        "Alta",
        f"[APROBADO] Socio {socio.numero} dado de ALTA. Cuenta {cuenta.id} generada.",
    )
    return socio


# ---------------------------------------------------------------------------
# Servicio: Rechazar socio
# ---------------------------------------------------------------------------

@transaction.atomic
def rechazar_socio(socio: Socios, motivo: str = "Solicitud rechazada") -> Socios:
    """
    Rechaza una solicitud PENDIENTE.
    - No genera cuenta corriente ni cargos
    - Limpia fechaAlta (el socio rechazado no tiene fecha de alta)
    """
    if not socio.esta_pendiente:
        if socio.esta_rechazado:
            raise ValidationError("El socio ya está RECHAZADO.")
        if socio.esta_activo:
            raise ValidationError("No se puede rechazar un socio en estado ALTA.")
        raise ValidationError("Solo se pueden rechazar solicitudes en estado PENDIENTE.")

    socio.activo = 3  # RECHAZADO
    socio.fechaAlta = None  # No tiene alta efectiva
    socio.save()

    _registrar_cambio("Rechazo", f"[RECHAZADO] Socio {socio.numero}: {motivo}")
    return socio


# ---------------------------------------------------------------------------
# Servicio: Dar de baja
# ---------------------------------------------------------------------------

@transaction.atomic
def dar_baja_socio(socio: Socios, motivo: str = "Baja Administrativa") -> Socios:
    """
    Da de baja al socio.
    - La CuentaCorriente siempre pasa a CERRADA
    - Si queda con deuda, el estado_cuenta reflejará MOROSO
    """
    if socio.esta_de_baja:
        raise ValidationError("El socio ya se encuentra de baja.")

    socio.activo = 0
    socio.fechaBaja = datetime.date.today()
    socio.save()

    # Cerrar la cuenta siempre
    try:
        cc = socio.cuenta_corriente
        cc.estado = CuentaCorriente.Estado.CERRADA
        cc.fecha_cierre = datetime.date.today()
        cc.save()
    except CuentaCorriente.DoesNotExist:
        pass  # Socio sin cuenta (pendiente que nunca fue aprobado)

    _registrar_cambio("Baja", motivo)
    return socio
