from decimal import Decimal
from django.db import transaction
from apps.cobranzas.models import CuentaCorriente, ConceptoCobro, Cargo
from apps.usuarios.models import Socios
from apps.cobranzas.services.cargos import crear_cargo

def generar_cuotas_mensuales(periodo: str):
    """
    Genera cargos para las cuentas activas en un periodo dado.
    Calcula si existe re-afiliacion menor a un año para cobrar matricula doble.
    """
    try:
        concepto_individual = ConceptoCobro.objects.get(codigo='CUOTA_INDIVIDUAL')
        concepto_familiar = ConceptoCobro.objects.get(codigo='CUOTA_FAMILIAR')
        concepto_temporada = ConceptoCobro.objects.get(codigo='CUOTA_TEMPORADA')
        concepto_matricula = ConceptoCobro.objects.get(codigo='MATRICULA')
    except ConceptoCobro.DoesNotExist:
        return {"error": "Faltan configurar Conceptos de Cobro base."}
        
    cuentas = CuentaCorriente.objects.filter(estado=CuentaCorriente.Estado.ACTIVA).select_related('socio_titular')
    
    # Precios por defecto (idealmente parametrizables en futuro)
    precio_ind = Decimal('1000.00')
    precio_fam = Decimal('1500.00')
    precio_temp = Decimal('500.00')
    precio_mat = Decimal('2000.00')
    
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
        fecha_vencimiento = date(year, month, 10) # Vence el 10
    except ValueError:
        return {"error": "El periodo debe tener formato YYYY-MM"}

    for cuenta in cuentas:
        resultados["cuentas_procesadas"] += 1
        socio = cuenta.socio_titular
        
        # Determinar el concepto basandose en la clase de socio o estado
        tipo_socio = (socio.tipo or "").lower()
        if 'temporada' in tipo_socio:
            concepto = concepto_temporada
            importe = precio_temp
        elif cuenta.tipo_cuenta == CuentaCorriente.TipoCuenta.FAMILIAR:
            concepto = concepto_familiar
            importe = precio_fam
        else:
            concepto = concepto_individual
            importe = precio_ind
            
        # Revisar si ya existe el cargo para no duplicar
        if Cargo.objects.filter(cuenta=cuenta, concepto=concepto, periodo=periodo).exists():
            resultados["cuotas_omitidas"] += 1
            continue
            
        try:
            with transaction.atomic():
                crear_cargo(cuenta, concepto, periodo, fecha_emision, fecha_vencimiento, importe)
                resultados["cuotas_creadas"] += 1
                
                # Check Reafiliacion menor a un ano segun fechaBaja de la ficha
                # Solo analizamos en el mes en que se dio de ALTA
                if socio.fechaAlta and socio.fechaAlta.year == year and socio.fechaAlta.month == month:
                    if socio.fechaBaja:
                        delta = socio.fechaAlta - socio.fechaBaja
                        if delta.days <= 365:
                            # Reafiliacion temprana, cobra matricula doble
                            if not Cargo.objects.filter(cuenta=cuenta, concepto=concepto_matricula, periodo=periodo).exists():
                                crear_cargo(cuenta, concepto_matricula, periodo, fecha_emision, fecha_vencimiento, precio_mat * Decimal('2.00'), "Matricula Doble por reafiliación temprana")
                                resultados["cuotas_creadas"] += 1
        except Exception as e:
            resultados["errores"].append(f"Error socio {socio.numero}: {str(e)}")
            
    return resultados
