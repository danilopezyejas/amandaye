import logging
import uuid

from django.core.exceptions import ValidationError as DomainValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger("amandaye.security")


class SafeAPIExceptionMixin:
    """Return public domain errors, but never database or unexpected exceptions."""

    def handle_exception(self, exc):
        if isinstance(exc, DomainValidationError):
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        if exception_handler(exc, self.get_exception_handler_context()) is not None:
            return super().handle_exception(exc)
        event_id = uuid.uuid4().hex
        # The exception text/traceback can contain SQL, credentials or personal data.
        logger.error(
            "api_operation_failed event_id=%s operation=%s error_type=%s",
            event_id, type(self).__name__, type(exc).__name__,
        )
        return Response(
            {"error": "No se pudo completar la operación.", "id": event_id},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
