from rest_framework import permissions


# =====================================================================
# ADD to dashboard/permissions.py — alongside the existing
# IsAdminOrReadOnly (leave that one untouched, LiveFestivalInfo still
# uses it).
# =====================================================================


class IsAdminUserType(permissions.BasePermission):
    """Full admin-only gate — unlike IsAdminOrReadOnly, this does NOT
    give read access to everyone. Live Darshan Management is an
    admin-only screen; volunteers/devotees read live status through the
    separate public `/live-darshan/` endpoint instead, not this
    ViewSet.

    "Admin" = Django is_staff OR user_type == "admin", same rule used
    everywhere else in the app.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_staff or getattr(user, "user_type", None) == "admin")

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    - Safe methods (GET, HEAD, OPTIONS): any authenticated user (admin,
      volunteer, devotee) can view live festival info / alerts.
    - Unsafe methods (POST, PUT, PATCH, DELETE): only admin/staff users can
      add, edit, or remove entries.

    "Admin" here means either the Django is_staff flag OR user_type ==
    "admin" (the app's own role field used everywhere else).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_staff or getattr(request.user, "user_type", None) == "admin"
        )