from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def alerta_view(request):
    data = {
        'color': 'verde',
        'type': 'sin riesgo',
        'expiration': '2025-05-21'
    }
    return Response(data)
