from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.cache import get_conditions


class ConditionsView(APIView):
    # Public environmental information; existing member/financial permissions are unchanged.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "conditions"
    http_method_names = ["get", "head", "options"]
    include_forecast = True

    def get(self, request):
        response = Response(get_conditions(include_forecast=self.include_forecast))
        # Cache provider data on the server, not a response with frozen age/stale values.
        response["Cache-Control"] = "no-store"
        return response


class StationsView(ConditionsView):
    include_forecast = False
