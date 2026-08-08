from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    - Safe methods (GET, HEAD, OPTIONS): any authenticated user.
    - Unsafe methods (POST, PUT, PATCH, DELETE): only admin/staff users.

    "Admin" here means either the Django is_staff flag OR user_type ==
    "admin" (the app's own role field used everywhere else — login,
    signup, notifications). Checking both means this still works even
    for admin accounts that were created without is_staff being set.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_staff or getattr(request.user, "user_type", None) == "admin"
        )