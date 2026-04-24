from rest_framework import serializers
from .models import Socios, Personas

class PersonasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Personas
        fields = '__all__'

class SociosSerializer(serializers.ModelSerializer):
    titular_nombre = serializers.SerializerMethodField()
    esta_pendiente = serializers.BooleanField(read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    esta_de_baja = serializers.BooleanField(read_only=True)

    class Meta:
        model = Socios
        fields = '__all__'

    def get_titular_nombre(self, obj):
        try:
            return str(obj)
        except Exception:
            return None

class PersonaPayloadSerializer(serializers.Serializer):
    Cedula = serializers.CharField(max_length=11)
    PrimerNombre = serializers.CharField(max_length=100)
    SegundoNombre = serializers.CharField(max_length=100, required=False, allow_blank=True)
    PrimerApellido = serializers.CharField(max_length=100)
    SegundoApellido = serializers.CharField(max_length=100, required=False, allow_blank=True)
    FechaNacimiento = serializers.DateField(required=False, allow_null=True)
    relacionTitular = serializers.CharField(max_length=20, required=False)
    Direccion = serializers.CharField(max_length=100, required=False, allow_blank=True)
    Telefono = serializers.CharField(max_length=9, required=False, allow_blank=True)
    Celular = serializers.CharField(max_length=12, required=False, allow_blank=True)
    Correo = serializers.EmailField(max_length=100, required=False, allow_blank=True)
    salud = serializers.CharField(max_length=20, required=False, allow_blank=True)

class SolicitudSocioSerializer(serializers.Serializer):
    datos_titular = PersonaPayloadSerializer()
    datos_familiares = PersonaPayloadSerializer(many=True, required=False)
