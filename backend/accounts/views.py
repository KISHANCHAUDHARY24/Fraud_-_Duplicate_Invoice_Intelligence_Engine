from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from .capabilities import Cap
from .models import Role, User
from .permissions import HasCapability
from .serializers import (
    ChangePasswordSerializer, CurrentUserSerializer, LoginSerializer, LogoutSerializer,
    RoleSerializer, UserCreateSerializer, UserSerializer, UserUpdateSerializer,
)


# ---------------------------------------------------------------------------
# Authentication: /api/auth/...
# ---------------------------------------------------------------------------
class LoginView(APIView):
    """POST {username, password} -> {access, refresh, user}"""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.login(request, **serializer.validated_data)
        return Response({**services.issue_tokens(user), "user": CurrentUserSerializer(user).data})


class RefreshView(TokenRefreshView):
    """POST {refresh} -> {access, refresh}. The old refresh token is blacklisted (rotation)."""


class LogoutView(APIView):
    """POST {refresh}. Blacklists the refresh token so it cannot be used again."""

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.logout(request, request.user, serializer.validated_data["refresh"])
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc
        return Response({"success": True, "message": "Logged out."})


class MeView(APIView):
    """GET the current user, including the capability list for the frontend."""

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """POST {old_password, new_password}. Logs out other devices; returns fresh tokens."""

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = services.change_password(request, request.user, serializer.validated_data["new_password"])
        return Response({"success": True, "message": "Password changed.", **tokens})


# ---------------------------------------------------------------------------
# User & role management (Admin): /api/users/, /api/roles/
# ---------------------------------------------------------------------------
class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    No DELETE: users are deactivated, never deleted, so their audit history stays intact.
    Filters: ?role=MANAGER&is_active=true&search=asha&ordering=-last_login
    """

    permission_classes = [HasCapability.of(Cap.USERS_MANAGE)]
    search_fields = ("username", "email", "first_name", "last_name", "department")
    ordering_fields = ("username", "date_joined", "last_login", "department")
    ordering = ("username",)

    def get_queryset(self):
        queryset = User.objects.select_related("role")
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role__code=role)
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=is_active == "true")
        return queryset

    def get_serializer_class(self):
        return {"create": UserCreateSerializer, "update": UserUpdateSerializer,
                "partial_update": UserUpdateSerializer}.get(self.action, UserSerializer)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user(request, request.user, **serializer.validated_data)
        return Response(UserSerializer(user).data, status=201)

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        user = services.update_user(request, request.user, user, **serializer.validated_data)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.set_user_active(request, request.user, self.get_object(), active=False)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.set_user_active(request, request.user, self.get_object(), active=True)
        return Response(UserSerializer(user).data)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasCapability.of(Cap.USERS_MANAGE)]
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    pagination_class = None
