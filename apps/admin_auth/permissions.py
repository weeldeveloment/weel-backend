from rest_framework.permissions import BasePermission
from django.contrib.auth import get_user_model

User = get_user_model()


class IsAdminUser(BasePermission):
    """
    Permission check for admin users (staff or superuser).
    Only Django admin users can access admin panel endpoints.
    """
    message = "Access denied. Admin privileges required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and (request.user.is_staff or request.user.is_superuser)
            and request.user.is_active
        )
