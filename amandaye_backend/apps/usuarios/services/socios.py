import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.usuarios.models import Socios, Personas, Socios_cambios
from apps.cobranzas.services.cuentas import crear_cuenta_corriente_para_titular
from apps.cobranzas.services.cargos import crear_cargo
from apps.cobranzas.models import ConceptoCobro, CuentaCorriente

def obtener_siguiente_numero_socio() -> int:
    ultimo = Socios.objects.order_by('-numero').first()
    return ultimo.numero + 1 if ultimo else 1000

@transaction.atomic
def crear_solicitud_socio(datos_titular: dict, datos_familiares: list = None) -> Socios:
    """
    Crea la solicitud de un socio nuevo en estado PENDIENTE.
    """
    if "Cedula" not in datos_titular or not datos_titular["Cedula"]:
        raise ValidationError("La cédula del titular es requerida.")

    if Personas.objects.filter(Cedula=datos_titular["Cedula"]).exists():
        raise ValidationError("Ya existe una persona con esta cédula.")

    if datos_familiares and len(datos_familiares) > 3:
        raise ValidationError("El núcleo familiar no puede exceder 3 integrantes adicionales (pareja + 2 hijos).")

    numero_socio = obtener_siguiente_numero_socio()
    
    # Crear persona titular
    Personas.objects.create(
        Cedula=datos_titular["Cedula"],
        numeroSocio=numero_socio,
        PrimerNombre=datos_titular.get("PrimerNombre", ""),
        SegundoNombre=datos_titular.get("SegundoNombre", ""),
        PrimerApellido=datos_titular.get("PrimerApellido", ""),
        SegundoApellido=datos_titular.get("SegundoApellido", ""),
        FechaNacimiento=datos_titular.get("FechaNacimiento", None),
        relacionTitular="TITULAR"
    )
    
    # Crear familiares si los hay
    tipo_socio = "FAMILIAR" if datos_familiares else "INDIVIDUAL"
    if datos_familiares:
        parejas = 0
        hijos = 0
        for f in datos_familiares:
            relacion = f.get("relacionTitular", "").upper()
            if relacion in ["PAREJA", "ESPOSO", "ESPOSA", "TUTOR"]:
                parejas += 1
            elif relacion == "HIJO":
                hijos += 1
                
            if parejas > 1:
                raise ValidationError("Solo se permite 1 pareja/tutor en el núcleo familiar.")
            if hijos > 2:
                raise ValidationError("Solo se permiten hasta 2 hijos en el núcleo familiar.")

            Personas.objects.create(
                Cedula=f.get("Cedula"),
                numeroSocio=numero_socio,
                PrimerNombre=f.get("PrimerNombre", ""),
                SegundoNombre=f.get("SegundoNombre", ""),
                PrimerApellido=f.get("PrimerApellido", ""),
                SegundoApellido=f.get("SegundoApellido", ""),
                FechaNacimiento=f.get("FechaNacimiento", None),
                relacionTitular=relacion
            )

    socio = Socios.objects.create(
        numero=numero_socio,
        activo=2, # PENDIENTE
        fechaAlta=datetime.date.today(), # provisional, se confirma al aprobar
        tipo=tipo_socio,
        cedulaTitular=datos_titular["Cedula"]
    )
    
    ultimo_cambio = Socios_cambios.objects.order_by('-id').first()
    nuevo_id = ultimo_cambio.id + 1 if ultimo_cambio else 1
    Socios_cambios.objects.create(
        id=nuevo_id,
        fecha=datetime.date.today(),
        accion="Alta",
        comentario=f"[SOLICITUD INGRESO] Socio {numero_socio} registrado en estado pendiente."
    )
    
    return socio

@transaction.atomic
def aprobar_socio(socio: Socios, generar_cargos_iniciales: bool = True) -> Socios:
    """
    Aprueba un socio pendiente, habilitando su estado y asignándole CuentaCorriente.
    """
    if not socio.esta_pendiente:
        if socio.esta_activo:
            raise ValidationError("El socio ya está en estado ALTA.")
        else:
            raise ValidationError("Socio no está PENDIENTE. Asegúrese de realizar el reingreso correspondiente.")

    # VALIDACION DE DEUDA HISTORICA (Reafiliación)
    cuenta_historica = CuentaCorriente.objects.filter(socio_titular=socio).first()
    if cuenta_historica:
        from apps.cobranzas.services.cuentas import obtener_estado_cuenta
        estado_cuenta = obtener_estado_cuenta(cuenta_historica)
        if estado_cuenta['saldo_total'] > 0:
            raise ValidationError(f"El socio arrastra una deuda pendiente de ${estado_cuenta['saldo_total']}. Debe abonar su saldo histórico antes de reafiliarse.")

    socio.activo = 1
    socio.fechaAlta = datetime.date.today()
    socio.save()
    
    # Crear CuentaCorriente
    cuenta = crear_cuenta_corriente_para_titular(socio)
    
    # Generar matrícula
    if generar_cargos_iniciales:
        try:
            concepto_mat = ConceptoCobro.objects.get(codigo="MATRICULA")
            from decimal import Decimal
            precio = concepto_mat.importe_por_defecto
            periodo = datetime.date.today().strftime('%Y-%m')
            
            # Chequeo reingreso (si estuvo de baja hace menos de 1 año)
            if socio.fechaBaja:
                delta = socio.fechaAlta - socio.fechaBaja
                if delta.days <= 365:
                    precio = precio * Decimal('2.00') # matricula doble
                    
            crear_cargo(
                cuenta=cuenta,
                concepto=concepto_mat,
                periodo=periodo,
                fecha_emision=datetime.date.today(),
                fecha_vencimiento=datetime.date.today() + datetime.timedelta(days=10),
                importe=precio,
                observaciones="Matrícula Automática de Alta / Reingreso"
            )
        except ConceptoCobro.DoesNotExist:
            pass # Sin seed the conceptos

        # GENERAR PRIMERA CUOTA MENSUAL
        codigo_cuota = "CUOTA_FAMILIAR" if socio.tipo and 'familiar' in socio.tipo.lower() else "CUOTA_INDIVIDUAL"
        try:
            concepto_cuota = ConceptoCobro.objects.get(codigo=codigo_cuota)
            crear_cargo(
                cuenta=cuenta,
                concepto=concepto_cuota,
                periodo=datetime.date.today().strftime('%Y-%m'),
                fecha_emision=datetime.date.today(),
                fecha_vencimiento=datetime.date.today() + datetime.timedelta(days=10),
                importe=concepto_cuota.importe_por_defecto,
                observaciones=f"Cuota Mensual ({socio.tipo})"
            )
        except ConceptoCobro.DoesNotExist:
            pass
            
    ultimo_cambio = Socios_cambios.objects.order_by('-id').first()
    nuevo_id = ultimo_cambio.id + 1 if ultimo_cambio else 1
    Socios_cambios.objects.create(
        id=nuevo_id,
        fecha=datetime.date.today(),
        accion="Alta",
        comentario=f"[APROBADO] Socio {socio.numero} dado de ALTA funcional. Cuenta {cuenta.id} generada."
    )
    return socio

@transaction.atomic
def dar_baja_socio(socio: Socios, motivo: str = "Baja Administrativa") -> Socios:
    """
    Da de baja al socio pero mantiene registro contable.
    """
    if socio.esta_de_baja:
        raise ValidationError("El socio ya se encuentra de baja.")
        
    socio.activo = 0
    socio.fechaBaja = datetime.date.today()
    socio.save()
    
    # Política CC: Se cierra la cuenta SI no hay deuda pendiente
    if hasattr(socio, 'cuenta_corriente') and socio.cuenta_corriente:
        cc = socio.cuenta_corriente
        from apps.cobranzas.services.cuentas import obtener_estado_cuenta
        estado = obtener_estado_cuenta(cc)
        if estado['saldo_total'] <= 0:
            cc.estado = CuentaCorriente.Estado.CERRADA
            cc.fecha_cierre = datetime.date.today()
            cc.save()
        # Si tiene saldo total > 0, se deja abierta en estado de reclamación/mora

    ultimo_cambio = Socios_cambios.objects.order_by('-id').first()
    nuevo_id = ultimo_cambio.id + 1 if ultimo_cambio else 1
    Socios_cambios.objects.create(
        id=nuevo_id,
        fecha=datetime.date.today(),
        accion="Baja",
        comentario=motivo
    )
    return socio
