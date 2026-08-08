from rest_framework import permissions

from .models import SOSAlert


def _is_admin(user):
    return bool(user.is_staff or getattr(user, "user_type", None) == "admin")


def _is_volunteer(user):
    return getattr(user, "user_type", None) == "volunteer"


def _is_devotee(user):
    return getattr(user, "user_type", None) == "devotee"


class SOSAlertPermission(permissions.BasePermission):
    """
    Emergency SOS access rules:

    - Must be logged in for everything (admin / volunteer / devotee).
    - GET (list/retrieve): any authenticated user — admin, volunteer, devotee.
    - POST (create): volunteers and admins can raise any alert type.
      Devotees can ONLY raise a Lost Child / Item alert — any other
      alert_type is rejected for a devotee at the permission layer.
    - PUT/PATCH/DELETE: admins can update/delete any alert; volunteers can
      only update/delete the alerts *they* raised; devotees can't
      update/delete alerts at all (object permission returns False).
    """

    message = "You are not allowed to raise this type of SOS alert."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method == "POST":
            if _is_admin(user) or _is_volunteer(user):
                return True
            if _is_devotee(user):
                return request.data.get("alert_type") == SOSAlert.AlertType.LOST_CHILD_ITEM
            return False

        # PUT/PATCH/DELETE — object-level check below decides; devotees
        # never reach edit/delete on SOS alerts at all.
        return _is_admin(user) or _is_volunteer(user)

    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            return True

        if _is_admin(user):
            return True

        if _is_volunteer(user):
            return obj.raised_by_id == user.id

        return False