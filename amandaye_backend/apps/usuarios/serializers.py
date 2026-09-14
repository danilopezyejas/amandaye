from collections.abc import Mapping

from rest_framework import serializers
from .models import Socios, Personas


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    field: "Este campo no está permitido." for field in sorted(unknown)
                })
        return super().to_internal_value(data)


class PersonasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Personas
        fields = (
            "Cedula", "numeroSocio", "PrimerNombre", "SegundoNombre",
            "PrimerApellido", "SegundoApellido", "FechaNacimiento", "Direccion",
            "Telefono", "Celular", "Correo", "relacionTitular", "salud", "llave",
            "estado_habilitacion", "fecha_ultimo_calculo_habilitacion",
        )
        read_only_fields = fields


class SociosSerializer(serializers.ModelSerializer):
    titular_nombre = serializers.SerializerMethodField()
    esta_pendiente = serializers.BooleanField(read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    esta_de_baja = serializers.BooleanField(read_only=True)

    class Meta:
        model = Socios
        fields = (
            "numero", "activo", "fechaSolicitud", "fechaAprobacion", "fechaAlta",
            "fechaBaja", "tipo_socio", "tipo_cuota", "cedulaTitular", "comentarios",
            "percha", "titular_nombre", "esta_pendiente", "esta_activo", "esta_de_baja",
        )
        read_only_fields = fields

    def get_titular_nombre(self, obj):
        return str(obj)


class PersonaPayloadSerializer(StrictInputSerializer):
    Cedula = serializers.CharField(max_length=11)
    PrimerNombre = serializers.CharField(max_length=100)
    SegundoNombre = serializers.CharField(max_length=100, required=False, allow_blank=True)
    PrimerApellido = serializers.CharField(max_length=100)
    SegundoApellido = serializers.CharField(max_length=100, required=False, allow_blank=True)
    FechaNacimiento = serializers.DateField()
    relacionTitular = serializers.ChoiceField(
        choices=("PAREJA", "ESPOSO", "ESPOSA", "TUTOR", "HIJO"), required=False,
    )
    Direccion = serializers.CharField(max_length=100, required=False, allow_blank=True)
    Telefono = serializers.CharField(max_length=9, required=False, allow_blank=True)
    Celular = serializers.CharField(max_length=12, required=False, allow_blank=True)
    Correo = serializers.EmailField(max_length=100, required=False, allow_blank=True)
    salud = serializers.CharField(max_length=20, required=False, allow_blank=True)


class SolicitudSocioSerializer(StrictInputSerializer):
    datos_titular = PersonaPayloadSerializer()
    datos_familiares = PersonaPayloadSerializer(many=True, required=False, max_length=3)

    def validate(self, attrs):
        titular = attrs["datos_titular"]
        for campo in ("Celular", "Direccion"):
            if not titular.get(campo):
                raise serializers.ValidationError({"datos_titular": {campo: "Este campo es obligatorio."}})
        cedulas = [titular["Cedula"]]
        for familiar in attrs.get("datos_familiares", []):
            if not familiar.get("relacionTitular"):
                raise serializers.ValidationError({"datos_familiares": "Indique la relación de cada familiar."})
            cedulas.append(familiar["Cedula"])
        if len(cedulas) != len(set(cedulas)):
            raise serializers.ValidationError("Cada integrante debe tener una cédula diferente.")
        return attrs


class BajaSocioInput(StrictInputSerializer):
    motivo = serializers.CharField(max_length=1000, trim_whitespace=True)
