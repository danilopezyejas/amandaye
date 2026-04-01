from rest_framework import serializers
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago

class ConceptoCobroSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConceptoCobro
        fields = '__all__'

class CuentaCorrienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaCorriente
        fields = '__all__'

class CargoSerializer(serializers.ModelSerializer):
    total_aplicado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    esta_vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cargo
        fields = '__all__'

class PagoSerializer(serializers.ModelSerializer):
    total_aplicado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    saldo_disponible = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Pago
        fields = '__all__'

class AplicacionPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AplicacionPago
        fields = '__all__'

class EstadoCuentaSerializer(serializers.Serializer):
    titular = serializers.IntegerField()
    tipo = serializers.CharField()
    saldo_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    deuda_vencida = serializers.DecimalField(max_digits=12, decimal_places=2)
    resumen_estados = serializers.DictField()
    cargos = CargoSerializer(many=True)
    pagos = PagoSerializer(many=True)
