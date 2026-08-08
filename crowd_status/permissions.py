# crowd_status/permissions.py — FULL FILE
from rest_framework.permissions import BasePermission


def _user_type(request):
    return getattr(request.user, "user_type", None) if request.user and request.user.is_authenticated else None


class IsDevoteeUser(BasePermission):
    def has_permission(self, request, view):
        return _user_type(request) == "devotee"


class IsVolunteerUser(BasePermission):
    def has_permission(self, request, view):
        return _user_type(request) == "volunteer"


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return _user_type(request) == "admin"


class IsAdminOrVolunteer(BasePermission):
    def has_permission(self, request, view):
        return _user_type(request) in ("admin", "volunteer")