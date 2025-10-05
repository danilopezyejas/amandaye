from django.urls import path
from . import views

urlpatterns = [
    path('', views.alerta_view, name='alerta'),
]