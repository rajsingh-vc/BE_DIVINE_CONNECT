from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Devotee
from .permissions import IsAdminOrReadOnly
from .serializers import DevoteeRegistrationSerializer, DevoteeSerializer


class DevoteeViewSet(viewsets.ModelViewSet):
    """Read (list/retrieve/search): any authenticated user — admin,
    volunteer, devotee. Write (create/update/partial_update/destroy):
    admins only — see IsAdminOrReadOnly.

    NOTE: the two extra actions below (`lookup`, `register`) are a
    deliberate exception, for the devotee-or-volunteer-facing "Online Seva
    Booking" form. They set their own `permission_classes` on the @action
    decorator, which DRF applies only to that action — IsAdminOrReadOnly
    above still governs create/update/partial_update/destroy exactly as
    before."""

    queryset = Devotee.objects.select_related("user").all()
    serializer_class = DevoteeSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["tier", "city"]
    search_fields = ["full_name", "devotee_code", "mobile"]
    ordering_fields = ["created_at", "visits", "total_donated"]

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """GET /api/devotees/search/?q=... — searches name and devotee ID."""
        from django.db.models import Q

        q = request.query_params.get("q", "")
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(devotee_code__icontains=q))
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="lookup", permission_classes=[permissions.IsAuthenticated])
    def lookup(self, request):
        """GET /api/devotees/lookup/?mobile=9999999999 — "Existing Devotees
        can enter mobile number to fetch their address" on the Online Seva
        Booking form. Open to any authenticated user (a devotee filling
        their own form, or a volunteer entering a walk-in), unlike the
        admin-only endpoints above. Returns null if no match."""
        mobile = request.query_params.get("mobile", "").strip()
        if not mobile:
            return Response({"detail": "mobile is required"}, status=status.HTTP_400_BAD_REQUEST)
        devotee = Devotee.objects.filter(mobile=mobile).first()
        if not devotee:
            return Response(None)
        return Response(DevoteeRegistrationSerializer(devotee).data)

    @action(detail=False, methods=["post"], url_path="register", permission_classes=[permissions.IsAuthenticated])
    def register(self, request):
        """POST /api/devotees/register/ — the Online Seva Booking form's
        save action. Usable by a devotee (self-service) or a volunteer
        (walk-in entry, with themselves recorded as the reference).
        Upserts by mobile number so re-entering an existing mobile updates
        that devotee instead of creating a duplicate.

        VIP registration: a volunteer can additionally pass `is_vip: true`
        in the request body to mark the devotee as VIP, and (via the VIP
        quick-add form) a `guest_count`. `is_vip` is enforced server-side,
        not just hidden in the UI — `tier` is read-only on
        DevoteeRegistrationSerializer (see serializers.py), so it can never
        arrive via `validated_data` no matter what a devotee or anyone else
        puts in the payload. The block near the bottom of this method is
        the ONLY place that can set `tier`, and it only fires when
        `user_type == "volunteer"`. Admins keep their own separate tier
        control on the main /admin/devotees console (DevoteeSerializer /
        the standard create/update endpoints, untouched by this action).

        `is_vip` is also passed to the serializer as context, which relaxes
        the normally-required fields (mobile, whatsapp, email, address,
        city, pincode) — the VIP quick-add form only collects a name and
        guest count."""
        is_vip = bool(request.data.get("is_vip"))

        serializer = DevoteeRegistrationSerializer(data=request.data, context={"is_vip": is_vip})
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)

        user = request.user
        user_type = getattr(user, "user_type", None)

        existing = None
        if user_type == "devotee":
            existing = Devotee.objects.filter(user=user).first()
        if existing is None and validated.get("mobile"):
            existing = Devotee.objects.filter(mobile=validated["mobile"]).first()

        # Don't let a blank "Referred by Volunteer" field wipe out an
        # attribution already recorded on a previous visit.
        if existing and validated.get("referred_by_volunteer") is None:
            validated.pop("referred_by_volunteer", None)

        devotee = existing or Devotee()
        for field, value in validated.items():
            setattr(devotee, field, value)

        if user_type == "devotee":
            devotee.user = user
        elif user_type == "volunteer" and not devotee.referred_by_volunteer_id:
            volunteer = getattr(user, "volunteer_profile_v2", None)
            if volunteer:
                devotee.referred_by_volunteer = volunteer

        # VIP is volunteer-only — see the docstring above for why this is
        # safe even though `is_vip` comes straight from request.data.
        if user_type == "volunteer" and is_vip:
            devotee.tier = "vip"  # swap for Devotee.Tier.VIP if your model defines a choices enum

        devotee.save()
        return Response(
            DevoteeRegistrationSerializer(devotee).data,
            status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED,
        )