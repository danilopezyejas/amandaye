from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.cobranzas.models import IntencionSaldo, Pago


class ImporteField(forms.DecimalField):
    """Accept the club's comma decimal notation as well as HTML's dot notation."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(',', '.')
        return super().to_python(value)


class CobroForm(forms.Form):
    fecha_pago = forms.DateField(
        label='Fecha del pago',
        input_formats=('%Y-%m-%d', '%d/%m/%Y'),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        initial=timezone.localdate,
    )
    importe_total = ImporteField(
        label='Importe recibido', max_digits=10, decimal_places=2,
        min_value=Decimal('0.01'), localize=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
    )
    medio_pago = forms.ChoiceField(label='Medio de pago', choices=Pago.MedioPago.choices)
    referencia = forms.CharField(label='Referencia', required=False, max_length=100)
    intencion_saldo = forms.ChoiceField(
        label='Saldo que quede sin aplicar', choices=IntencionSaldo.choices,
        initial=IntencionSaldo.APLICAR,
        help_text='Si sobra dinero después de cubrir cargos, indique si queda como anticipo o pendiente de aplicación.',
    )

    def clean_importe_total(self):
        value = self.cleaned_data['importe_total']
        return value.quantize(Decimal('0.01'))


class SaldoForm(forms.Form):
    intencion_saldo = forms.ChoiceField(
        label='Saldo que quede sin aplicar', choices=IntencionSaldo.choices,
        initial=IntencionSaldo.APLICAR,
    )


class DistribucionForm(forms.Form):
    """Only server-selected charges can receive an editable amount."""

    def __init__(self, filas, disponible, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filas = filas
        self.disponible = disponible
        for row in filas:
            self.fields[f"cargo_{row['cargo_id']}"] = ImporteField(
                label=f"Aplicar al cargo {row['cargo_id']}",
                max_digits=10, decimal_places=2, min_value=Decimal('0.00'),
                max_value=Decimal(row['saldo']), initial=Decimal(row['importe']),
                widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': row['saldo']}),
            )

    def clean(self):
        data = super().clean()
        if sum(data.values(), Decimal('0.00')) > self.disponible:
            raise forms.ValidationError('La distribución supera el importe disponible.')
        return data

    def aplicaciones(self):
        return [
            {'cargo_id': row['cargo_id'], 'importe': str(self.cleaned_data[f"cargo_{row['cargo_id']}"])}
            for row in self.filas if self.cleaned_data[f"cargo_{row['cargo_id']}"] > 0
        ]

    def filas_con_campos(self):
        return [(row, self[f"cargo_{row['cargo_id']}"]) for row in self.filas]


class PendientesForm(forms.Form):
    socio = forms.RegexField(r'^[0-9]{1,10}$', label='Número de socio', required=False)
    solicitudes_desde = forms.DateField(label='Solicitudes desde', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    solicitudes_hasta = forms.DateField(label='Solicitudes hasta', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    intencion = forms.ChoiceField(label='Pagos: intención del saldo', required=False,
        choices=[('', 'Todas las intenciones')] + list(IntencionSaldo.choices))
    vencimiento_hasta = forms.DateField(label='Deuda vencida: vencimiento hasta', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    habilitacion = forms.ChoiceField(label='Habilitación registrada', required=False,
        choices=[('', 'No habilitados y suspendidos'), ('TODOS', 'Todos los estados'),
                 ('NO_HABILITADO', 'No habilitado'), ('SUSPENDIDO', 'Suspendido'),
                 ('REVOCADO', 'Revocado'), ('HABILITADO', 'Habilitado')])

    def __init__(self, *args, can_socios, can_cuentas, can_personas, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('solicitudes_desde', 'solicitudes_hasta'):
            if not can_socios:
                self.fields.pop(name)
        for name in ('intencion', 'vencimiento_hasta'):
            if not can_cuentas:
                self.fields.pop(name)
        if not can_personas:
            self.fields.pop('habilitacion')

    def clean_socio(self):
        value = self.cleaned_data['socio']
        if value and int(value) > 2147483647:
            raise forms.ValidationError('El número de socio es demasiado grande.')
        return int(value) if value else None

    def clean(self):
        data = super().clean()
        desde, hasta = data.get('solicitudes_desde'), data.get('solicitudes_hasta')
        if desde and hasta and desde > hasta:
            raise forms.ValidationError('La fecha inicial de solicitudes no puede superar la final.')
        return data
