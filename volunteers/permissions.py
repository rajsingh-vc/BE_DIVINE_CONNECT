from rest_framework import permissions


def is_admin_user(user) -> bool:
    """
    Single source of truth for "is this user an admin" across the app.

    A user counts as admin if ANY of these are true:
      - Django's is_staff flag
      - Django's is_superuser flag (createsuperuser sets this but not
        always is_staff, depending on how the account was made)
      - the app's own user_type == "admin" field

    Centralizing this avoids the three checks drifting out of sync across
    different permission classes.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(
        user.is_staff
        or getattr(user, "is_superuser", False)
        or getattr(user, "user_type", None) == "admin"
    )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Volunteer records / Duties — core CRUD access rules:

    - Safe methods (GET list/retrieve): any authenticated user (admin,
      volunteer, devotee) can view the volunteer directory / duty list.
    - Unsafe methods (POST/PUT/PATCH/DELETE) on the base CRUD endpoints:
      admins only. This does NOT apply to the custom sub-actions
      (apply / register / reference-action / admin-action / accept /
      start / complete / request-help / swap-respond / swap-candidates)
      — those set their own permission_classes on the @action decorator
      and take precedence over this class-level check.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_admin_user(request.user)