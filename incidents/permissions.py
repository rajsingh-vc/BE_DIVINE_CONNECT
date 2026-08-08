from rest_framework import permissions


def _is_admin(user):
    return bool(user.is_staff or getattr(user, "user_type", None) == "admin")


def _is_volunteer(user):
    return getattr(user, "user_type", None) == "volunteer"


class IncidentReportPermission(permissions.BasePermission):
    """
    Incident Log access rules:

    - Must be logged in for everything (admin / volunteer / devotee).
    - GET (list/retrieve): any authenticated user — admin, volunteer, devotee.
    - POST (create): volunteers and admins only (devotees cannot file reports).
    - PUT/PATCH/DELETE: admins can update/delete any report; volunteers can
      only update/delete the reports *they* created.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method == "POST":
            return _is_admin(user) or _is_volunteer(user)

        # PUT / PATCH / DELETE — final say happens in has_object_permission,
        # but only admins and volunteers are ever allowed to reach it.
        return _is_admin(user) or _is_volunteer(user)

    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            return True

        if _is_admin(user):
            return True

        if _is_volunteer(user):
            return obj.reported_by_id == user.id

        return False