from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Devotee records — core CRUD access rules:

    - Safe methods (GET list/retrieve/search): any authenticated user
      (admin, volunteer, devotee) can view the devotee directory.
    - Unsafe methods (POST/PUT/PATCH/DELETE): admins only.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_staff or getattr(request.user, "user_type", None) == "admin"
        )