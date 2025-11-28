from django.urls import path
from . import views

urlpatterns = [
    path('buscar/', views.buscar_persona, name='buscar_persona'),
    path('detalle/<int:pk>/', views.detalle_persona, name='detalle_persona'),
]
