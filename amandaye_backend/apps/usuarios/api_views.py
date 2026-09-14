from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .api_errors import SafeAPIExceptionMixin
from .models import Socios
from .permissions import ClubPermissions
from .serializers import BajaSocioInput, SociosSerializer, SolicitudSocioSerializer
from .services.socios import aprobar_socio, crear_solicitud_socio, dar_baja_socio


class MeView(SafeAPIExceptionMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "roles": [group.name for group in user.groups.all()],
        })


class SociosViewSet(SafeAPIExceptionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Socios.objects.order_by("pk")
    serializer_class = SociosSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "usuarios.view_socios",
        "retrieve": "usuarios.view_socios",
        "aprobar": "usuarios.puede_aprobar_socio",
        "dar_baja": "usuarios.puede_dar_baja_socio",
    }
    throttle_scope = None

    @action(
        detail=False, methods=["post"], url_path="solicitudes",
        permission_classes=[AllowAny], throttle_classes=[ScopedRateThrottle],
        throttle_scope="solicitudes", authentication_classes=[],
    )
    def crear_solicitud(self, request):
        serializer = SolicitudSocioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            crear_solicitud_socio(**serializer.validated_data)
        except ValidationError as exc:
            # A public caller must not discover whether a person is already a member.
            if getattr(exc, "code", None) != "duplicate_person":
                raise
        return Response(
            {"mensaje": "Solicitud recibida. Secretaría revisará los datos ingresados."},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="aprobar")
    def aprobar(self, request, pk=None):
        socio = aprobar_socio(
            self.get_object(), generar_cargos_iniciales=True, usuario=request.user,
        )
        return Response(SociosSerializer(socio).data)

    @action(detail=True, methods=["post"], url_path="dar-baja")
    def dar_baja(self, request, pk=None):
        entrada = BajaSocioInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        socio = dar_baja_socio(
            self.get_object(), motivo=entrada.validated_data["motivo"],
            usuario=request.user,
        )
        return Response(SociosSerializer(socio).data)
