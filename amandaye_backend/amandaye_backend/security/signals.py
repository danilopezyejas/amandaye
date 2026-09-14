import logging
from axes.signals import user_locked_out
from django.dispatch import receiver
from rest_framework.exceptions import Throttled
from rest_framework.request import Request

logger = logging.getLogger("amandaye.security")


@receiver(user_locked_out)
def authentication_locked(sender, request, **kwargs):
    logger.warning("authentication_locked")
    if isinstance(request, Request):
        raise Throttled(wait=900, detail="Demasiados intentos. Inténtelo de nuevo más tarde.")
