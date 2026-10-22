"""Static user guidance, selected by the resolved page; no database access."""
from django import template

register = template.Library()

GUIDES = {
    'inicio': ('Administración del club', ['Elegí el módulo que necesitás o entrá a Gestión diaria para atender a un socio.', 'Los botones y acciones disponibles dependen de tus permisos. Si falta un acceso, consultá al administrador.', 'En los listados podés buscar, filtrar y abrir un registro. Seleccionar filas no ejecuta acciones: revisá la acción antes de pulsar Ir.']),
    'login': ('Acceso al sistema', ['Ingresá con tu cuenta del club. No existen credenciales predeterminadas.', 'Si no podés ingresar, consultá al administrador para recuperar el acceso. Evitá repetir intentos con una contraseña incorrecta.']),
    'dashboard': ('Panel de pendientes', ['Usá los filtros y pulsá Aplicar filtros; Limpiar filtros vuelve al listado inicial.', 'Cada sección tiene sus propias páginas de 25 registros. Los conteos incluyen todos los resultados filtrados.', 'Pagos con saldo distingue anticipos, aplicaciones pendientes y pagos sin clasificar. La deuda no se compensa automáticamente.', 'Habilitaciones filtra por estado registrado. Los motivos se evalúan hoy sin guardar cambios; Todos los estados permite revisar también personas habilitadas.']),
    'buscar_socios': ('Buscar socio o familiar', ['Buscá por número de socio, cédula o nombre completo, según tus permisos.', 'Verificá el número de socio antes de abrir la ficha: puede haber nombres iguales.', 'La búsqueda por un familiar lleva a la ficha de su grupo.']),
    'ficha_socio': ('Ficha del socio', ['Comprobá titular y grupo familiar antes de registrar movimientos.', 'Deuda y dinero sin aplicar se muestran separados. Revisá cargos, pagos y aplicaciones para entender el saldo.', 'Registrar cobro crea un nuevo ingreso. Aplicar saldo utiliza dinero que ya fue registrado.', 'El historial reúne eventos atribuibles; algunos movimientos antiguos pueden no tener operador o vínculo disponible.', 'Los motivos de habilitación son una evaluación actual de consulta; no cambian por sí solos el estado registrado.']),
    'nuevo_cobro': ('Registrar un cobro', ['Ingresá fecha, importe, medio de pago y referencia. Proponer distribución todavía no registra el pago.', 'Ajustá los importes por cargo; cero deja ese cargo sin pagar. Si sobra dinero, indicá si es anticipo o aplicación pendiente.', 'Revisá la distribución y confirmá una sola vez para registrar el pago y emitir el comprobante interno PDF.', 'La revisión vence a los 30 minutos. Si cambiaron los saldos, revisá nuevamente. Un reintento idéntico no duplica la operación.']),
    'aplicar_saldo_pago': ('Aplicar un pago existente', ['Este flujo usa el saldo de un pago ya registrado: no crea otro ingreso.', 'Revisá los cargos y los importes, luego confirmá la distribución.', 'El comprobante original conserva su contenido. Las aplicaciones nuevas se consultan en la ficha y el historial.']),
    'socios': ('Socios y solicitudes', ['Buscá al socio y comprobá su titular y estado antes de actuar.', 'Aprobar procesa solicitudes pendientes y puede crear cuenta y cargos según la cuota configurada. Rechazar no equivale a dar de baja.', 'Dar de baja cierra la afiliación; no borra deuda ni movimientos históricos. Reactivar inicia un nuevo período de alta.', 'Cambiar tipo de cuota requiere la acción específica. Revisá la selección y la pantalla de confirmación antes de continuar.']),
    'personas': ('Personas, familia y habilitación', ['Personas contiene los datos individuales; Socios identifica la afiliación del grupo.', 'Comprobá el número de socio y la relación con el titular antes de modificar un vínculo.', 'En la ficha podés revisar aprobaciones de profesor, avales y embarcaciones según permisos.', 'El diagnóstico distingue edad, antigüedad, datos faltantes y aprobaciones. Consultarlo no guarda un nuevo estado de habilitación.']),
    'historico_socios': ('Histórico de socios', ['Consultá los registros históricos y seleccioná los que querés comparar.', 'Graficar registros seleccionados utiliza esa selección; comprobá los períodos antes de interpretar la evolución.']),
    'cuentacorriente': ('Cuentas corrientes', ['Cada cuenta reúne los cargos y pagos de un socio.', 'Deuda pendiente es lo que falta pagar; saldo disponible es dinero recibido aún sin asignar. No son el mismo valor.', 'Abrí la ficha en Gestión diaria para registrar un cobro o aplicar un pago existente. Una cuenta cerrada puede conservar deuda histórica.']),
    'conceptocobro': ('Conceptos de cobro', ['Los conceptos identifican qué se cobra. Revisá nombre e importe antes de guardar.', 'Modificar el catálogo no corrige cargos ya emitidos. Para corregir movimientos históricos usá las operaciones autorizadas.', 'La programación de tarifas por fecha de vigencia todavía no está disponible.']),
    'cargo': ('Cargos', ['Un cargo representa un importe a pagar por una cuenta. Revisá concepto, período, vencimiento e importe.', 'Los cargos emitidos conservan su historia: no cambies un importe histórico para corregirlo.', 'Anular cargos seleccionados requiere permiso y una selección correcta. La anulación no equivale a devolver dinero.']),
    'pago': ('Pagos', ['Un pago registra dinero recibido. Aplicarlo asigna ese dinero a uno o más cargos.', 'Para registrar y aplicar en un solo recorrido, usá Registrar cobro en Gestión diaria.', 'Aplicar saldo utiliza el remanente del pago. Revisá la cuenta, el cargo y el importe antes de confirmar.', 'Resumen mensual permite consultar movimientos del período con el permiso correspondiente.']),
    'aplicacionpago': ('Aplicaciones y reversiones', ['Una aplicación vincula parte de un pago con un cargo. No es un nuevo ingreso.', 'Para corregir una asignación, seleccioná la aplicación y usá Revertir; revisá la confirmación y el motivo solicitado.', 'La reversión conserva la auditoría y libera el importe para volver a aplicarlo. No registra una devolución de dinero.']),
    'auth': ('Cuentas de acceso y permisos', ['Las cuentas de acceso pertenecen a operadores; no son las cuentas corrientes de los socios.', 'Asigná únicamente los permisos necesarios para el trabajo de cada persona.', 'Los grupos reúnen permisos. Cambiarlos afecta las acciones que sus integrantes pueden realizar.']),
}

@register.inclusion_tag('gestion/ayuda.html', takes_context=True)
def ayuda_contextual(context):
    request = context.get('request')
    match = getattr(request, 'resolver_match', None)
    name = getattr(match, 'url_name', '') or ''
    namespace = getattr(match, 'namespace', '')
    opts = context.get('opts')
    model = getattr(opts, 'model_name', '')
    key = 'inicio'
    if name in ('login', 'password_change', 'password_change_done'):
        key = 'login'
    elif namespace == 'gestion':
        key = name if name in GUIDES else 'inicio'
    elif model in GUIDES:
        key = model
    elif name.startswith('usuarios_'):
        key = next((k for k in ('historico_socios', 'personas', 'socios') if k in name), 'socios')
    elif name.startswith('cobranzas_') or 'pago' in name or 'resumen' in name:
        key = next((k for k in ('aplicacionpago', 'cuentacorriente', 'conceptocobro', 'cargo', 'pago') if k in name), 'pago')
    elif name.startswith('auth_'):
        key = 'auth'
    elif context.get('app_label') == 'usuarios':
        key = 'socios'
    elif context.get('app_label') == 'cobranzas':
        key = 'cuentacorriente'
    title, steps = GUIDES[key]
    return {'help_title': title, 'help_steps': steps}
