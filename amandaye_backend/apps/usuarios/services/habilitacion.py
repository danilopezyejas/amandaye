import datetime
from django.utils import timezone
from apps.usuarios.models import Personas, Socios
from apps.cobranzas.models import Cargo, CuentaCorriente

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

def evaluar_condiciones(*, revocado, socio_existe, activo=False, temporada=False,
                        nacimiento=None, fecha_base=None, aprobacion=False, aval=False,
                        cargos=(), hoy):
    """Pure policy: primitive facts in, state and ordered reason codes out; no IO."""
    if revocado:
        return {'estado': 'REVOCADO', 'motivos': [('REVOCADO', 'Habilitación revocada; requiere revisión de Comisión Directiva.', 'Revisión')]}
    if not socio_existe:
        return {'estado': 'NO_HABILITADO', 'motivos': [('SIN_SOCIO', 'No existe un socio vinculado a este número.', 'Datos')]}
    periodos = set(_get_ultimos_tres_periodos(hoy))
    recientes = [(periodo, estado) for periodo, estado in cargos if periodo in periodos]
    if len({periodo for periodo, _ in recientes}) == 3 and all(
            estado in (Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL) for _, estado in recientes):
        return {'estado': 'SUSPENDIDO', 'motivos': [('DEUDA', 'Cargos pendientes en los tres últimos períodos, incluido el actual.', 'Cuenta')]}
    motivos = []
    if not activo:
        motivos.append(('SOCIO_INACTIVO', 'El socio no está en ALTA.', 'Socio'))
    if temporada:
        motivos.append(('TEMPORADA', 'La cuota de temporada no otorga habilitación permanente.', 'Cuota'))
    if nacimiento is None:
        motivos.append(('SIN_NACIMIENTO', 'Falta la fecha de nacimiento.', 'Datos'))
    elif _calcular_edad(nacimiento, hoy) < 18:
        motivos.append(('EDAD', 'Debe cumplir 18 años.', 'Espera por edad'))
    if fecha_base is None:
        motivos.append(('SIN_ALTA', 'Falta la fecha de alta o aprobación.', 'Datos'))
    elif (hoy - fecha_base).days < 365:
        motivos.append(('ANTIGUEDAD', 'Debe completar 365 días desde el alta actual.', 'Espera por antigüedad'))
    if not aprobacion:
        motivos.append(('PROFESOR', 'Falta aprobación de profesor válida para el alta y grupo actuales.', 'Aprobación'))
    if not aval:
        motivos.append(('AVAL', 'Falta aval activo de Comisión Directiva.', 'Aval'))
    return {'estado': 'NO_HABILITADO' if motivos else 'HABILITADO', 'motivos': motivos}


def evaluar_habilitacion(persona, socio, hoy):
    """Read existing relationships; never saves or infers historical approvals."""
    if persona.estado_habilitacion == 'REVOCADO' or socio is None:
        return evaluar_condiciones(revocado=persona.estado_habilitacion == 'REVOCADO',
                                   socio_existe=socio is not None, hoy=hoy)
    cuenta = getattr(socio, 'cuenta_corriente', None)
    cargos = [(c.periodo, c.estado) for c in cuenta.cargos.all()] if cuenta else []
    fecha_base = socio.fechaAlta or socio.fechaAprobacion
    return evaluar_condiciones(
        revocado=False, socio_existe=True, activo=socio.activo == 1,
        temporada=socio.tipo_cuota == 'TEMPORADA', nacimiento=persona.FechaNacimiento,
        fecha_base=fecha_base, hoy=hoy, cargos=cargos,
        aprobacion=bool(fecha_base and any(ap.fecha >= fecha_base and ap.numero_socio_momento == socio.numero
                                         for ap in persona.aprobaciones_profesor.all())),
        aval=any(av.activo for av in persona.avales_cd.all()),
    )


def preparar_diagnosticos(personas, hoy=None):
    """Batch the read-only diagnosis for a page or family, not the entire registry."""
    from django.db.models import Prefetch, prefetch_related_objects
    hoy = hoy or timezone.localdate()
    personas = list(personas)
    prefetch_related_objects(personas, 'aprobaciones_profesor', 'avales_cd')
    socios = {s.numero: s for s in Socios.objects.filter(numero__in={p.numeroSocio for p in personas})
              .select_related('cuenta_corriente').prefetch_related(Prefetch(
                  'cuenta_corriente__cargos', queryset=Cargo.objects.filter(periodo__in=_get_ultimos_tres_periodos(hoy))))}
    labels = dict(Personas.ESTADO_HABILITACION)
    for persona in personas:
        resultado = evaluar_habilitacion(persona, socios.get(persona.numeroSocio), hoy)
        persona.diagnostico = {**resultado, 'estado_label': labels[resultado['estado']], 'fecha': hoy,
                              'difiere': resultado['estado'] != persona.estado_habilitacion}
    return personas


def _calcular_estado_individual(persona, socio, hoy) -> str:
    return evaluar_habilitacion(persona, socio, hoy)['estado']

def recalcular_habilitacion_persona(persona: Personas) -> str:
    hoy = timezone.localdate()
    socio = Socios.objects.filter(numero=persona.numeroSocio).select_related('cuenta_corriente').prefetch_related('cuenta_corriente__cargos').first()
    
    persona = Personas.objects.prefetch_related('aprobaciones_profesor', 'avales_cd').get(Cedula=persona.Cedula)

    nuevo_estado = _calcular_estado_individual(persona, socio, hoy)
    
    persona.estado_habilitacion = nuevo_estado
    persona.fecha_ultimo_calculo_habilitacion = timezone.now()
    persona.save(update_fields=['estado_habilitacion', 'fecha_ultimo_calculo_habilitacion'])
    
    return nuevo_estado

def recalcular_habilitados(socio_id=None) -> dict:
    hoy = timezone.localdate()
    
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
