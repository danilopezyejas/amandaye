(() => {
  'use strict';
  const actions = {
    aprobar_socios_seleccionados: 'Aprueba solicitudes pendientes; puede crear la cuenta y los cargos correspondientes a la cuota.',
    rechazar_socios_seleccionados: 'Rechaza las solicitudes seleccionadas. Comprobá que sean solicitudes pendientes.',
    dar_baja_socios_seleccionados: 'Da de baja la afiliación. Conserva la deuda y el historial.',
    reactivar_socios_seleccionados: 'Reactiva la afiliación e inicia un nuevo período de alta.',
    cambiar_cuota_socios_seleccionados: 'Abre el cambio de tipo de cuota para los socios seleccionados.',
    anular_cargos_seleccionados: 'Anula los cargos seleccionados según las reglas del servicio; no devuelve dinero.',
    revertir_aplicaciones: 'Deshace la asignación del pago al cargo, conserva la auditoría y no registra una devolución.',
    graficar_seleccionados: 'Compara en un gráfico los registros históricos seleccionados.',
    delete_selected: 'Elimina los registros seleccionados si el modelo y tus permisos lo permiten. Revisá la confirmación.'
  };
  const labels = {
    'Registrar cobro': 'Registra dinero nuevo y permite distribuirlo entre cargos antes de confirmar.',
    'Aplicar saldo': 'Asigna dinero ya registrado a cargos; no crea otro pago.',
    'Aplicar Saldo': 'Asigna dinero ya registrado a cargos; no crea otro pago.',
    'Proponer distribución': 'Calcula una propuesta editable. Todavía no guarda el pago.',
    'Revisar distribución': 'Muestra los importes definitivos antes de registrar la operación.',
    'Confirmar cobro y emitir comprobante': 'Guarda el pago y sus aplicaciones y genera el comprobante interno PDF.',
    'Confirmar aplicación de saldo': 'Guarda la distribución del saldo del pago existente.',
    'Volver a ajustar': 'Regresa a la distribución para corregir importes antes de confirmar.',
    'Aplicar filtros': 'Actualiza las listas y sus conteos con los filtros elegidos.',
    'Limpiar filtros': 'Quita los filtros y vuelve a la primera página.',
    'Ver persona': 'Abre los datos individuales y sus vínculos, según tus permisos.',
    'Ver solicitud': 'Abre la solicitud para consultar su estado y datos.',
    'Revisar aprobación': 'Abre la persona para revisar la aprobación del profesor del alta actual.',
    'Revisar aval': 'Abre la persona para revisar el aval de Comisión Directiva.',
    'Guardar': 'Guarda los cambios del formulario. Revisá los datos antes de continuar.',
    'Guardar y continuar editando': 'Guarda los cambios y mantiene abierto este registro.',
    'Guardar y añadir otro': 'Guarda este registro y abre un formulario nuevo.',
    'Historial': 'Consulta los cambios administrativos registrados para este objeto.',
    'Resumen mensual': 'Consulta los movimientos del período con los permisos correspondientes.'
  };
  Object.assign(labels, {
    'Aplicar a Cargo': labels['Aplicar saldo'],
    '🟢 Aplicar saldo a cargo': labels['Aplicar saldo'],
    'Resumen Mensual': labels['Resumen mensual'],
    'Añadir Pago': 'Registra dinero recibido. Para distribuirlo y emitir PDF en un solo flujo, usá Gestión diaria.',
    'Buscar': 'Filtra los registros por el texto ingresado.',
    'Sí, estoy seguro': 'Confirma la operación indicada en esta pantalla. Revisá los registros y su efecto antes de continuar.'
  });
  const fields = {
    importe: 'Importe del cargo o de la operación. Usá hasta dos decimales.',
    importe_total: 'Dinero recibido en este pago, antes de asignarlo a cargos.',
    importe_aplicado: 'Parte del pago que se asignará a este cargo.',
    fecha_vencimiento: 'Fecha límite del cargo. Se considera vencido a partir del día siguiente.',
    periodo: 'Período al que corresponde el cargo, con formato año-mes.',
    numeroSocio: 'Número de la afiliación del grupo al que pertenece esta persona.',
    cedulaTitular: 'Cédula de la persona titular del grupo. Verificá su vínculo con el socio.',
    tipo_cuota: 'Categoría de cobro del socio. Los cambios de socios existentes se realizan mediante la acción específica.'
  };
  let active = null;
  let timer;
  let serial = 0;
  function hide() {
    if (!active) return;
    active.tip.hidden = true;
    active = null;
  }
  function addHint(element, getText) {
    if (element.dataset.clubHint) return;
    element.dataset.clubHint = 'true';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'club-tip-button';
    button.textContent = '?';
    button.setAttribute('aria-label', 'Ayuda sobre ' + (element.labels?.[0]?.textContent || element.textContent || element.value || 'esta función').trim());
    const tip = document.createElement('span');
    tip.id = 'club-tooltip-' + (++serial);
    tip.className = 'club-tooltip';
    tip.role = 'tooltip';
    tip.hidden = true;
    tip.textContent = getText();
    button.setAttribute('aria-describedby', tip.id);
    element.insertAdjacentElement('afterend', button);
    document.body.append(tip);
    const show = () => {
      clearTimeout(timer);
      hide();
      tip.textContent = getText();
      tip.hidden = false;
      const box = button.getBoundingClientRect();
      tip.style.left = Math.max(12, Math.min(box.left, window.innerWidth - tip.offsetWidth - 12)) + 'px';
      tip.style.top = Math.max(12, Math.min(box.bottom + 6, window.innerHeight - tip.offsetHeight - 12)) + 'px';
      active = {button, tip};
    };
    const later = () => { timer = setTimeout(() => { if (active?.tip === tip) hide(); }, 180); };
    button.addEventListener('mouseenter', show);
    button.addEventListener('mouseleave', later);
    button.addEventListener('focus', show);
    button.addEventListener('blur', later);
    button.addEventListener('click', show);
    tip.addEventListener('mouseenter', () => clearTimeout(timer));
    tip.addEventListener('mouseleave', later);
    element.addEventListener('change', () => { tip.textContent = getText(); });
  }
  document.querySelectorAll('#content a, #content button, #content input[type=submit]').forEach(el => {
    const text = (el.value || el.textContent).trim().replace(/\s+/g, ' ');
    if (labels[text]) addHint(el, () => labels[text]);
  });
  document.querySelectorAll('select[name=action]').forEach(el => addHint(el, () => actions[el.value] || 'Seleccioná una acción y revisá las filas marcadas antes de pulsar Ir.'));
  Object.entries(fields).forEach(([name, text]) => {
    document.querySelectorAll('[name="' + name + '"]').forEach(el => addHint(el, () => text));
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  document.addEventListener('click', event => { if (active && !active.button.contains(event.target) && !active.tip.contains(event.target)) hide(); });
  window.addEventListener('resize', hide);
  window.addEventListener('scroll', () => {
    if (!active) return;
    const {button, tip} = active;
    const box = button.getBoundingClientRect();
    tip.style.left = Math.max(12, Math.min(box.left, window.innerWidth - tip.offsetWidth - 12)) + 'px';
    tip.style.top = Math.max(12, Math.min(box.bottom + 6, window.innerHeight - tip.offsetHeight - 12)) + 'px';
  }, true);
})();
