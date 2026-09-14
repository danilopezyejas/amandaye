from decimal import Decimal

from rest_framework import serializers
from apps.usuarios.serializers import StrictInputSerializer
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .services.cargos import crear_cargo
from .services.pagos import registrar_pago


class ConceptoCobroSerializer(serializers.ModelSerializer):
    importe_por_defecto = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.00"), required=False,
    )

    class Meta:
        model = ConceptoCobro
        fields = (
            "id", "codigo", "nombre", "descripcion", "importe_por_defecto",
            "activo", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class CuentaCorrienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaCorriente
        fields = (
            "id", "socio_titular", "tipo_cuenta", "estado", "fecha_apertura",
            "fecha_cierre", "created_at", "updated_at",
        )
        read_only_fields = fields


class ImmutableMovementSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        raise serializers.ValidationError("Use una operación autorizada de anulación o reversión.")


class CargoSerializer(ImmutableMovementSerializer):
    importe = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
    )
    periodo = serializers.RegexField(regex=r"^\d{4}-(0[1-9]|1[0-2])$", max_length=7)
    observaciones = serializers.CharField(max_length=2000, required=False, allow_blank=True, allow_null=True)
    total_aplicado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    esta_vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cargo
        fields = (
            "id", "cuenta", "concepto", "periodo", "fecha_emision",
            "fecha_vencimiento", "importe", "estado", "observaciones",
            "created_at", "updated_at", "total_aplicado", "saldo_pendiente",
            "esta_vencido", "registrado_por", "anulado_por", "fecha_anulacion",
        )
        read_only_fields = (
            "id", "estado", "created_at", "updated_at", "registrado_por",
            "anulado_por", "fecha_anulacion",
        )

    def validate(self, attrs):
        if attrs["fecha_vencimiento"] < attrs["fecha_emision"]:
            raise serializers.ValidationError({"fecha_vencimiento": "No puede ser anterior a la emisión."})
        return attrs

    def create(self, validated_data):
        return crear_cargo(**validated_data, usuario=self.context["request"].user)


class PagoSerializer(ImmutableMovementSerializer):
    importe_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
    )
    observaciones = serializers.CharField(max_length=2000, required=False, allow_blank=True, allow_null=True)
    total_aplicado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    saldo_disponible = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Pago
        fields = (
            "id", "cuenta", "fecha_pago", "importe_total", "medio_pago",
            "referencia", "observaciones", "registrado_por", "created_at",
            "updated_at", "total_aplicado", "saldo_disponible",
        )
        read_only_fields = ("id", "registrado_por", "created_at", "updated_at")

    def create(self, validated_data):
        return registrar_pago(**validated_data, usuario=self.context["request"].user)


class AplicacionPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AplicacionPago
        fields = (
            "id", "pago", "cargo", "importe_aplicado", "estado", "fecha_reversion",
            "motivo_reversion", "registrado_por", "revertido_por", "created_at", "updated_at",
        )
        read_only_fields = fields


class AplicarPagoInput(StrictInputSerializer):
    cargo_id = serializers.IntegerField(min_value=1)
    importe = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
    )


class AnularCargoInput(StrictInputSerializer):
    observaciones = serializers.CharField(max_length=1000, trim_whitespace=True)


class RevertirAplicacionInput(StrictInputSerializer):
    motivo = serializers.CharField(max_length=1000, trim_whitespace=True)


class RecaudacionInput(StrictInputSerializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("desde") and attrs.get("hasta") and attrs["desde"] > attrs["hasta"]:
            raise serializers.ValidationError("El fin del período debe ser posterior al inicio.")
        return attrs


class EstadoCuentaSerializer(serializers.Serializer):
    titular = serializers.IntegerField()
    tipo = serializers.CharField()
    saldo_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    deuda_vencida = serializers.DecimalField(max_digits=12, decimal_places=2)
    resumen_estados = serializers.DictField()
    cargos = CargoSerializer(many=True)
    pagos = PagoSerializer(many=True)
