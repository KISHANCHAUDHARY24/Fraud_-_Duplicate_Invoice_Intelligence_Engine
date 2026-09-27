from rest_framework.permissions import BasePermission, IsAuthenticated

from .capabilities import user_can


class HasCapability(BasePermission):
    """
    Allow the request if the user has ANY of the listed capabilities.

        permission_classes = [HasCapability.of(Cap.USERS_MANAGE)]
    """

    required = ()
    message = "You do not have permission to perform this action."

    @classmethod
    def of(cls, *capabilities):
        name = "HasCapability_" + "_".join(c.replace(".", "_") for c in capabilities)
        return type(name, (cls,), {"required": capabilities})

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_can(request.user, *self.required))


class ActionCapabilityMixin:
    """
    Per-action capabilities for ViewSets:

        action_capabilities = {
            "list": (Cap.INVOICES_VIEW,),
            "create": (Cap.INVOICES_CREATE,),
        }

    Actions not in the map are DENIED (fail closed), so a newly added action
    cannot become public by accident.
    """

    action_capabilities = {}

    def get_permissions(self):
        required = self.action_capabilities.get(self.action)
        if required is None:
            return [IsAuthenticated(), _DenyAll()]
        return [IsAuthenticated(), HasCapability.of(*required)()]


class _DenyAll(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        return False
