from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """
    One of the four business roles. Rows are created by a data migration
    (accounts/migrations/0002_seed_roles.py), so they always exist.
    """

    class Code(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        AP_OFFICER = "AP_OFFICER", "Accounts Payable Officer"
        MANAGER = "MANAGER", "Manager"
        AUDITOR = "AUDITOR", "Auditor"

    code = models.CharField(max_length=20, unique=True, choices=Code.choices)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Custom user. Extends Django's built-in user (username, password hash,
    first/last name, is_active, ...) with a business role and department.
    """

    email = models.EmailField("email address", unique=True)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users",
        help_text="Business role. Superusers without a role are treated as Administrators.",
    )
    department = models.CharField(max_length=100, blank=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]

    @property
    def role_code(self):
        if self.role is not None:
            return self.role.code
        return Role.Code.ADMIN if self.is_superuser else None

    def has_role(self, *codes):
        """user.has_role("MANAGER", "AUDITOR") -> True if the user holds any of them."""
        return self.role_code in codes

    def __str__(self):
        return self.get_full_name() or self.username
