from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.cobranzas.models import CuentaCorriente, ConceptoCobro, Cargo
from apps.usuarios.models import Socios
from apps.cobranzas.services.cargos import crear_cargo

def generar_cuotas_mensuales(periodo: str):
    """
    Genera cargos para las cuentas activas en un periodo dado.
    Los importes se obtienen siempre del campo importe_por_defecto del ConceptoCobro.
    """
    try:
        concepto_individual = ConceptoCobro.objects.get(codigo='CUOTA_INDIVIDUAL')
        concepto_familiar = ConceptoCobro.objects.get(codigo='CUOTA_FAMILIAR')
        concepto_temporada = ConceptoCobro.objects.get(codigo='CUOTA_TEMPORADA')
        concepto_matricula = ConceptoCobro.objects.get(codigo='MATRICULA')
    except ConceptoCobro.DoesNotExist as e:
        return {"error": f"Faltan configurar Conceptos de Cobro base: {e}"}

    # Validar que los importes por defecto sean válidos
    for concepto in [concepto_individual, concepto_familiar, concepto_temporada, concepto_matricula]:
        if concepto.importe_por_defecto <= 0:
            return {"error": f"El importe por defecto de '{concepto.codigo}' debe ser mayor a 0."}
        
    cuentas = CuentaCorriente.objects.filter(estado=CuentaCorriente.Estado.ACTIVA).select_related('socio_titular')
    
    resultados = {
        "cuentas_procesadas": 0,
        "cuotas_creadas": 0,
        "cuotas_omitidas": 0,
        "errores": []
    }
    
    from datetime import date
    import calendar
    
    try:
        year, month = map(int, periodo.split('-'))
        _, last_day = calendar.monthrange(year, month)
        fecha_emision = date(year, month, 1)
        fecha_vencimiento = date(year, month, 10)  # Vence el 10
    except ValueError:
        return {"error": "El periodo debe tener formato YYYY-MM"}

    # Generar snapshot historico del mes si no existe
    from apps.usuarios.models import Historico_socios, Personas
    if not Historico_socios.objects.filter(fecha=fecha_emision).exists():
        total_activos = Socios.objects.filter(activo=1).count()
        familiares = Socios.objects.filter(activo=1, tipo_socio='FAMILIAR').count()
        individuales = Socios.objects.filter(activo=1, tipo_socio='INDIVIDUAL').count()
        personas_activas = Personas.objects.filter(numeroSocio__in=Socios.objects.filter(activo=1).values('numero')).count()
        
        Historico_socios.objects.create(
            fecha=fecha_emision,
            familiar=familiares,
            individual=individuales,
            total=total_activos,
            personas=personas_activas
        )

    for cuenta in cuentas:
        resultados["cuentas_procesadas"] += 1
        socio = cuenta.socio_titular
        
        if socio.tipo_cuota == 'EXONERADO':
            resultados["cuotas_omitidas"] += 1
            continue

        if socio.tipo_cuota == 'TEMPORADA':
            concepto = concepto_temporada
        elif socio.tipo_socio == 'FAMILIAR':
            concepto = concepto_familiar
        else:
            concepto = concepto_individual

        importe = concepto.importe_por_defecto
        
        if socio.tipo_cuota == 'BECA':
            importe = round(importe * Decimal('0.50'), 2)
            
        # Revisar si ya existe el cargo para no duplicar
        if Cargo.objects.filter(cuenta=cuenta, concepto=concepto, periodo=periodo).exists():
            resultados["cuotas_omitidas"] += 1
            continue
            
        try:
            with transaction.atomic():
                crear_cargo(cuenta, concepto, periodo, fecha_emision, fecha_vencimiento, importe)
                resultados["cuotas_creadas"] += 1
                
                # Check Reafiliacion menor a un año según fechaBaja de la ficha
                if socio.fechaAprobacion and socio.fechaAprobacion.year == year and socio.fechaAprobacion.month == month:
                    if socio.fechaBaja:
                        delta = socio.fechaAprobacion - socio.fechaBaja
                        if delta.days <= 365:
                            importe_mat = concepto_matricula.importe_por_defecto * Decimal('2.00')
                            if not Cargo.objects.filter(cuenta=cuenta, concepto=concepto_matricula, periodo=periodo).exists():
                                crear_cargo(cuenta, concepto_matricula, periodo, fecha_emision, fecha_vencimiento, importe_mat, "Matrícula Doble por reafiliación temprana")
                                resultados["cuotas_creadas"] += 1
        except Exception as e:
            resultados["errores"].append(f"Error socio {socio.numero}: {str(e)}")
            
    return resultados
