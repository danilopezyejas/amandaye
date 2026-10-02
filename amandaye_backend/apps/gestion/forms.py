import datetime
from decimal import Decimal

from django import forms

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
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=datetime.date.today,
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
