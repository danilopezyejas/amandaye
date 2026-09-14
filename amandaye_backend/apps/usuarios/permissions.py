from rest_framework.permissions import BasePermission


class ClubPermissions(BasePermission):
    """Every internal operation must declare its own Django permission."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        action = getattr(view, "action", request.method.lower())
        required = getattr(view, "permission_map", {}).get(action)
        return bool(required and user.has_perm(required))
