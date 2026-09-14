from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.usuarios.api_errors import SafeAPIExceptionMixin
from apps.usuarios.permissions import ClubPermissions
from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .serializers import (
    CuentaCorrienteSerializer, ConceptoCobroSerializer, CargoSerializer,
    PagoSerializer, AplicacionPagoSerializer, EstadoCuentaSerializer,
    AplicarPagoInput, AnularCargoInput, RevertirAplicacionInput, RecaudacionInput,
)
from .services.cuentas import obtener_estado_cuenta
from .services.cargos import anular_cargo
from .services.pagos import aplicar_pago, revertir_aplicacion


class ConceptoCobroViewSet(SafeAPIExceptionMixin, viewsets.ModelViewSet):
    queryset = ConceptoCobro.objects.order_by("pk")
    serializer_class = ConceptoCobroSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "cobranzas.view_conceptocobro",
        "retrieve": "cobranzas.view_conceptocobro",
        "create": "cobranzas.add_conceptocobro",
        "update": "cobranzas.change_conceptocobro",
        "partial_update": "cobranzas.change_conceptocobro",
        "destroy": "cobranzas.delete_conceptocobro",
    }


class CuentaCorrienteViewSet(SafeAPIExceptionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CuentaCorriente.objects.order_by("pk")
    serializer_class = CuentaCorrienteSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "cobranzas.view_cuentacorriente",
        "retrieve": "cobranzas.view_cuentacorriente",
        "estado_cuenta": "cobranzas.view_cuentacorriente",
    }

    @action(detail=True, methods=["get"], url_path="estado-cuenta")
    def estado_cuenta(self, request, pk=None):
        estado = obtener_estado_cuenta(self.get_object())
        return Response(EstadoCuentaSerializer(estado).data)


class CargoViewSet(SafeAPIExceptionMixin, mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Cargo.objects.order_by("pk")
    serializer_class = CargoSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "cobranzas.view_cargo",
        "retrieve": "cobranzas.view_cargo",
        "create": "cobranzas.add_cargo",
        "anular": "cobranzas.puede_anular_cargo",
    }

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        entrada = AnularCargoInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        cargo = anular_cargo(
            self.get_object(), observaciones=entrada.validated_data["observaciones"],
            usuario=request.user,
        )
        return Response(CargoSerializer(cargo).data)


class PagoViewSet(SafeAPIExceptionMixin, mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Pago.objects.order_by("pk")
    serializer_class = PagoSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "cobranzas.view_pago",
        "retrieve": "cobranzas.view_pago",
        "create": "cobranzas.add_pago",
        "aplicar": "cobranzas.puede_aplicar_pago",
    }

    @action(detail=True, methods=["post"])
    def aplicar(self, request, pk=None):
        entrada = AplicarPagoInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        pago = self.get_object()
        cargo = get_object_or_404(Cargo, pk=entrada.validated_data["cargo_id"])
        aplicacion = aplicar_pago(
            pago, cargo, entrada.validated_data["importe"], usuario=request.user,
        )
        return Response(AplicacionPagoSerializer(aplicacion).data, status=status.HTTP_201_CREATED)


class AplicacionPagoViewSet(SafeAPIExceptionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AplicacionPago.objects.order_by("pk")
    serializer_class = AplicacionPagoSerializer
    permission_classes = [ClubPermissions]
    permission_map = {
        "list": "cobranzas.view_aplicacionpago",
        "retrieve": "cobranzas.view_aplicacionpago",
        "revertir": "cobranzas.puede_revertir_aplicacion_pago",
    }

    @action(detail=True, methods=["post"])
    def revertir(self, request, pk=None):
        entrada = RevertirAplicacionInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        revertir_aplicacion(
            self.get_object(), motivo=entrada.validated_data["motivo"], usuario=request.user,
        )
        return Response({"status": "Aplicación revertida y cargo recalculado."})


class ReporteCuentasConDeudaView(SafeAPIExceptionMixin, APIView):
    permission_classes = [ClubPermissions]
    permission_map = {"get": "cobranzas.puede_ver_resumen_cobranzas"}

    def get(self, request):
        cuentas = CuentaCorriente.objects.filter(
            estado=CuentaCorriente.Estado.ACTIVA,
            cargos__estado__in=[Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL],
        ).distinct()
        return Response(CuentaCorrienteSerializer(cuentas, many=True).data)


class ReporteRecaudacionView(SafeAPIExceptionMixin, APIView):
    permission_classes = [ClubPermissions]
    permission_map = {"get": "cobranzas.puede_ver_resumen_cobranzas"}

    def get(self, request):
        entrada = RecaudacionInput(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        pagos = Pago.objects.all()
        if entrada.validated_data.get("desde"):
            pagos = pagos.filter(fecha_pago__gte=entrada.validated_data["desde"])
        if entrada.validated_data.get("hasta"):
            pagos = pagos.filter(fecha_pago__lte=entrada.validated_data["hasta"])
        total = pagos.aggregate(total=Sum("importe_total"))["total"] or 0
        return Response({"recaudacion_total": total})
