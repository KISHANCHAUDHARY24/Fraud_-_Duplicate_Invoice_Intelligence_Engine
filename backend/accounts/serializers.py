from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .capabilities import capabilities_for
from .models import Role, User


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "code", "name", "description")


class UserSerializer(serializers.ModelSerializer):
    """Read representation used in lists, details and the login response."""

    full_name = serializers.SerializerMethodField()
    role = serializers.CharField(source="role_code", read_only=True)
    role_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "full_name",
            "role", "role_name", "department", "is_active", "last_login", "date_joined",
        )
        read_only_fields = fields

    def get_full_name(self, user):
        return user.get_full_name() or user.username

    def get_role_name(self, user):
        return user.role.name if user.role_id else ("Administrator" if user.is_superuser else None)


class CurrentUserSerializer(UserSerializer):
    """The logged-in user, plus the capability list React uses to build its menus."""

    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("permissions",)
        read_only_fields = fields

    def get_permissions(self, user):
        return sorted(capabilities_for(user))


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different from the current one."})
        validate_password(attrs["new_password"], self.context["request"].user)
        return attrs


class _RoleCodeField(serializers.SlugRelatedField):
    def __init__(self, **kwargs):
        super().__init__(slug_field="code", queryset=Role.objects.all(), **kwargs)


class UserCreateSerializer(serializers.ModelSerializer):
    role = _RoleCodeField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "department", "password")

    def validate(self, attrs):
        # Validate the password against the would-be user (e.g. "not similar to username").
        validate_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    role = _RoleCodeField()

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "department")
