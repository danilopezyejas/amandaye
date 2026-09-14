from django.contrib import admin
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import include, path
from .security.authentication import LoginView, RefreshView


def home(request):
    return redirect("/login/")


def custom_404(request, exception=None):
    return HttpResponseNotFound("Página no encontrada.")


urlpatterns = [
    path("", home), path("login/", admin.site.login, name="login"), path("admin/", admin.site.urls),
    path("api/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("apps/alertas/", include("apps.alertas.urls")),
    path("api/usuarios/", include("apps.usuarios.urls")),
    path("api/", include("apps.usuarios.api_urls")),
    path("api/cobranzas/", include("apps.cobranzas.urls")),
]
handler404 = custom_404
