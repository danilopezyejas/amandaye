from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from rest_framework.views import APIView

from .models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from .serializers import (
    CuentaCorrienteSerializer, ConceptoCobroSerializer, 
    CargoSerializer, PagoSerializer, AplicacionPagoSerializer,
    EstadoCuentaSerializer
)

from .services.cuentas import obtener_estado_cuenta
from .services.cargos import anular_cargo
from .services.pagos import aplicar_pago, revertir_aplicacion

class ConceptoCobroViewSet(viewsets.ModelViewSet):
    queryset = ConceptoCobro.objects.all()
    serializer_class = ConceptoCobroSerializer

class CuentaCorrienteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CuentaCorriente.objects.all()
    serializer_class = CuentaCorrienteSerializer

    @action(detail=True, methods=['get'], url_path='estado-cuenta')
    def estado_cuenta(self, request, pk=None):
        cuenta = self.get_object()
        estado = obtener_estado_cuenta(cuenta)
        serializer = EstadoCuentaSerializer(estado)
        return Response(serializer.data)

class CargoViewSet(viewsets.ModelViewSet):
    queryset = Cargo.objects.all()
    serializer_class = CargoSerializer

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        cargo = self.get_object()
        observaciones = request.data.get('observaciones', '')
        try:
            cargo_anulado = anular_cargo(cargo, observaciones)
            return Response(CargoSerializer(cargo_anulado).data)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer

    @action(detail=True, methods=['post'])
    def aplicar(self, request, pk=None):
        pago = self.get_object()
        cargo_id = request.data.get('cargo_id')
        importe = request.data.get('importe')
        
        if not cargo_id or not importe:
            return Response({"error": "cargo_id e importe son requeridos"}, status=status.HTTP_400_BAD_REQUEST)
            
        cargo = get_object_or_404(Cargo, pk=cargo_id)
        
        try:
            from decimal import Decimal
            importe_dec = Decimal(str(importe))
            aplicacion = aplicar_pago(pago, cargo, importe_dec)
            return Response(AplicacionPagoSerializer(aplicacion).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AplicacionPagoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AplicacionPago.objects.all()
    serializer_class = AplicacionPagoSerializer

    @action(detail=True, methods=['post'])
    def revertir(self, request, pk=None):
        aplicacion = self.get_object()
        try:
            revertir_aplicacion(aplicacion)
            return Response({"status": "Aplicacion revertida y cargo recalculado."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ReporteCuentasConDeudaView(APIView):
    def get(self, request):
        cuentas = CuentaCorriente.objects.filter(
            estado=CuentaCorriente.Estado.ACTIVA, 
            cargos__estado__in=[Cargo.Estado.PENDIENTE, Cargo.Estado.PARCIAL]
        ).distinct()
        serializer = CuentaCorrienteSerializer(cuentas, many=True)
        return Response(serializer.data)

class ReporteRecaudacionView(APIView):
    def get(self, request):
        desde = request.query_params.get('desde')
        hasta = request.query_params.get('hasta')
        pagos = Pago.objects.all()
        if desde:
            pagos = pagos.filter(fecha_pago__gte=desde)
        if hasta:
            pagos = pagos.filter(fecha_pago__lte=hasta)
            
        total = pagos.aggregate(total=Sum('importe_total'))['total'] or 0
        return Response({"recaudacion_total": total})
