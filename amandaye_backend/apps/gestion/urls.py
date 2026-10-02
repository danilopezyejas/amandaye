from django.urls import path

from . import views

app_name = 'gestion'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('socios/', views.buscar_socios, name='buscar_socios'),
    path('socios/<int:numero>/', views.ficha_socio, name='ficha_socio'),
    path('socios/<int:numero>/cobro/', views.nuevo_cobro, name='nuevo_cobro'),
    path('comprobantes/pagos/<int:pago_id>/', views.comprobante_pago, name='comprobante_pago'),
]
