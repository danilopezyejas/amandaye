from axes.handlers.proxy import AxesProxyHandler
from django.conf import settings
from django.http import JsonResponse
from rest_framework.exceptions import Throttled
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def client_ip(request):
    if settings.TRUST_PROXY_HEADERS:
        return request.META.get("HTTP_X_REAL_IP", request.META.get("REMOTE_ADDR"))
    return request.META.get("REMOTE_ADDR")


def lockout_response(request, credentials=None, *args, **kwargs):
    response = JsonResponse({"detail": "Demasiados intentos. Inténtelo de nuevo más tarde."}, status=429)
    response["Retry-After"] = "900"
    return response


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        request = self.context["request"]
        credentials = {self.username_field: attrs.get(self.username_field, "")}
        if not AxesProxyHandler.is_allowed(request, credentials):
            raise Throttled(wait=900, detail="Demasiados intentos. Inténtelo de nuevo más tarde.")
        data = super().validate(attrs)
        # Reset Axes attempts without Django's user_logged_in signal, which writes last_login.
        AxesProxyHandler.user_logged_in(sender=type(self.user), request=request, user=self.user)
        return data


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"
