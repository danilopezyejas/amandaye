from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConceptoCobroViewSet, CuentaCorrienteViewSet, CargoViewSet, 
    PagoViewSet, AplicacionPagoViewSet, ReporteCuentasConDeudaView,
    ReporteRecaudacionView
)

router = DefaultRouter()
router.register(r'conceptos-cobro', ConceptoCobroViewSet, basename='conceptos')
router.register(r'cuentas', CuentaCorrienteViewSet, basename='cuentas')
router.register(r'cargos', CargoViewSet, basename='cargos')
router.register(r'pagos', PagoViewSet, basename='pagos')
router.register(r'aplicaciones', AplicacionPagoViewSet, basename='aplicaciones')

urlpatterns = [
    path('', include(router.urls)),
    path('reportes/cuentas-con-deuda/', ReporteCuentasConDeudaView.as_view(), name='cuentas-con-deuda'),
    path('reportes/recaudacion/', ReporteRecaudacionView.as_view(), name='recaudacion'),
]
