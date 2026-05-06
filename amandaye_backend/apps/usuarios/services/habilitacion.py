import datetime
from django.utils import timezone
from apps.usuarios.models import Personas, Socios
from apps.cobranzas.models import Cargo

def _calcular_edad(fecha_nacimiento: datetime.date, hoy: datetime.date) -> int:
    if not fecha_nacimiento:
        return 0
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )

def _get_ultimos_tres_periodos(hoy: datetime.date):
    periodos = []
    d = hoy
    for _ in range(3):
        periodos.append(d.strftime('%Y-%m'))
        d = d.replace(day=1) - datetime.timedelta(days=1)
    return periodos

def _calcular_estado_individual(persona, socio, hoy) -> str:
    # 1. Revocado
    if persona.estado_habilitacion == 'REVOCADO':
        return 'REVOCADO'

    if not socio:
        return 'NO_HABILITADO'

    # 2. Suspendido
    try:
        cuenta = getattr(socio, 'cuenta_corriente', None)
        if cuenta:
            periodos = _get_ultimos_tres_periodos(hoy)
            cargos = list(cuenta.cargos.all())
            cargos_en_periodos = [c for c in cargos if c.periodo in periodos]
            
            periodos_con_cargo = set(c.periodo for c in cargos_en_periodos)
            
            if len(periodos_con_cargo) == 3:
                todos_adeudados = all(c.estado in [Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL] for c in cargos_en_periodos)
                if todos_adeudados:
                    return 'SUSPENDIDO'
    except Exception:
        pass

    # 3. Habilitado
    cond_a = socio.activo == 1
    cond_b = socio.tipo_cuota != 'TEMPORADA'
    cond_c = _calcular_edad(persona.FechaNacimiento, hoy) >= 18
    
    cond_d = False
    if socio.fechaAprobacion:
        cond_d = (hoy - socio.fechaAprobacion).days >= 365

    cond_e = False
    if socio.fechaAprobacion:
        for ap in persona.aprobaciones_profesor.all():
            if ap.fecha >= socio.fechaAprobacion and ap.numero_socio_momento == socio.numero:
                cond_e = True
                break

    cond_f = any(av.activo for av in persona.avales_cd.all())

    if cond_a and cond_b and cond_c and cond_d and cond_e and cond_f:
        return 'HABILITADO'

    # 4. NO_HABILITADO
    return 'NO_HABILITADO'

def recalcular_habilitacion_persona(persona: Personas) -> str:
    hoy = datetime.date.today()
    socio = Socios.objects.filter(numero=persona.numeroSocio).select_related('cuenta_corriente').prefetch_related('cuenta_corriente__cargos').first()
    
    persona = Personas.objects.prefetch_related('aprobaciones_profesor', 'avales_cd').get(Cedula=persona.Cedula)

    nuevo_estado = _calcular_estado_individual(persona, socio, hoy)
    
    persona.estado_habilitacion = nuevo_estado
    persona.fecha_ultimo_calculo_habilitacion = timezone.now()
    persona.save(update_fields=['estado_habilitacion', 'fecha_ultimo_calculo_habilitacion'])
    
    return nuevo_estado

def recalcular_habilitados(socio_id=None) -> dict:
    hoy = datetime.date.today()
    
    qs_personas = Personas.objects.prefetch_related('aprobaciones_profesor', 'avales_cd')
    if socio_id:
        qs_personas = qs_personas.filter(numeroSocio=socio_id)
        
    personas = list(qs_personas)
    
    socios_nums = set(p.numeroSocio for p in personas if p.numeroSocio)
    qs_socios = Socios.objects.filter(numero__in=socios_nums).select_related('cuenta_corriente').prefetch_related('cuenta_corriente__cargos')
    socios_dict = {s.numero: s for s in qs_socios}
    
    resultados = {
        'evaluados': len(personas),
        'habilitados': 0,
        'no_habilitados': 0,
        'suspendidos': 0,
        'revocados': 0,
    }
    
    personas_a_actualizar = []
    ahora = timezone.now()
    
    for p in personas:
        socio = socios_dict.get(p.numeroSocio)
        nuevo_estado = _calcular_estado_individual(p, socio, hoy)
        
        if nuevo_estado == 'HABILITADO': resultados['habilitados'] += 1
        elif nuevo_estado == 'NO_HABILITADO': resultados['no_habilitados'] += 1
        elif nuevo_estado == 'SUSPENDIDO': resultados['suspendidos'] += 1
        elif nuevo_estado == 'REVOCADO': resultados['revocados'] += 1
        
        if p.estado_habilitacion != nuevo_estado or p.fecha_ultimo_calculo_habilitacion is None:
            p.estado_habilitacion = nuevo_estado
            p.fecha_ultimo_calculo_habilitacion = ahora
            personas_a_actualizar.append(p)
            
    if personas_a_actualizar:
        Personas.objects.bulk_update(personas_a_actualizar, ['estado_habilitacion', 'fecha_ultimo_calculo_habilitacion'])
        
    return resultados
