"""amandaye_backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html')),
    path('admin/', admin.site.urls),
    
    # JWT Authentication Endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path('apps/alertas/', include('apps.alertas.urls')),
    # path('api/brevet/', include('apps.brevet.urls')),
    # path('api/horarios/', include('apps.horarios.urls')),
    path('api/usuarios/', include('apps.usuarios.urls')),
    path('api/', include('apps.usuarios.api_urls')),
    path('api/cobranzas/', include('apps.cobranzas.urls')),
    # path('api/amandaye_web/', include('amandaye_web.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
