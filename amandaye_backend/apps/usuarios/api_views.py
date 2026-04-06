from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import Socios, Personas
from .serializers import SociosSerializer, PersonasSerializer, SolicitudSocioSerializer
from .services.socios import crear_solicitud_socio, aprobar_socio, dar_baja_socio

class SociosViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Rutas:
    GET /api/socios/
    GET /api/socios/{id}/
    POST /api/socios/solicitudes/
    POST /api/socios/{id}/aprobar/
    POST /api/socios/{id}/dar-baja/
    """
    queryset = Socios.objects.all()
    serializer_class = SociosSerializer

    @action(detail=False, methods=['post'], url_path='solicitudes')
    def crear_solicitud(self, request):
        serializer = SolicitudSocioSerializer(data=request.data)
        if serializer.is_valid():
            try:
                socio = crear_solicitud_socio(
                    datos_titular=serializer.validated_data.get('datos_titular'),
                    datos_familiares=serializer.validated_data.get('datos_familiares')
                )
                return Response(SociosSerializer(socio).data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        socio = self.get_object()
        generar_cargos_iniciales = request.data.get('generar_cargos_iniciales', True)
        try:
            socio_aprobado = aprobar_socio(socio, generar_cargos_iniciales=generar_cargos_iniciales)
            return Response(SociosSerializer(socio_aprobado).data)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='dar-baja')
    def dar_baja(self, request, pk=None):
        socio = self.get_object()
        motivo = request.data.get('motivo', 'Baja Administrativa solicitada via API')
        try:
            socio_baja = dar_baja_socio(socio, motivo=motivo)
            return Response(SociosSerializer(socio_baja).data)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
