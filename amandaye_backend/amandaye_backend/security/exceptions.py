import logging
import uuid
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("amandaye.security")


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    event_id = uuid.uuid4().hex
    logger.error("request_failed event_id=%s exception_type=%s", event_id, type(exc).__name__)
    return Response({"detail": "No se pudo completar la operación.", "id": event_id}, status=500)
