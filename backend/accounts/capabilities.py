"""
Role-based access control: the permission matrix from docs/authentication.md §4 as code.

This is the ONLY place that decides what each role may do.
  * Backend views check it through accounts.permissions.HasCapability.
  * GET /api/auth/me/ sends the user's list to React, which uses it only to
    show/hide UI. The backend check is what actually protects the data.

Object-level rules ("only invoices you submitted", "only approvals assigned to
you") are enforced separately in each view's queryset / service.
"""


class Cap:
    USERS_MANAGE = "users.manage"
    SETTINGS_VIEW = "settings.view"
    SETTINGS_MANAGE = "settings.manage"

    VENDORS_VIEW = "vendors.view"
    VENDORS_CREATE = "vendors.create"
    VENDORS_EDIT = "vendors.edit"
    BANK_ACCOUNTS_VIEW = "bank_accounts.view"
    BANK_ACCOUNTS_MANAGE = "bank_accounts.manage"

    INVOICES_VIEW = "invoices.view"
    INVOICES_CREATE = "invoices.create"
    INVOICES_SUBMIT = "invoices.submit"
    INVOICES_REANALYZE = "invoices.reanalyze"

    FRAUD_VIEW = "fraud.view"
    ALERTS_VIEW = "alerts.view"
    ALERTS_ASSIGN = "alerts.assign"
    ALERTS_RESOLVE = "alerts.resolve"

    APPROVALS_VIEW = "approvals.view"
    APPROVALS_DECIDE = "approvals.decide"
    APPROVALS_ESCALATE = "approvals.escalate"
    PAYMENTS_VIEW = "payments.view"
    PAYMENTS_SIMULATE = "payments.simulate"

    AUDIT_VIEW = "audit.view"
    ANALYTICS_VIEW = "analytics.view"
    REPORTS_EXPORT = "reports.export"


# Shared by every role.
_EVERYONE = {Cap.VENDORS_VIEW, Cap.INVOICES_VIEW, Cap.FRAUD_VIEW, Cap.ALERTS_VIEW}

ROLE_CAPABILITIES = {
    "ADMIN": _EVERYONE | {
        Cap.USERS_MANAGE, Cap.SETTINGS_VIEW, Cap.SETTINGS_MANAGE,
        Cap.VENDORS_CREATE, Cap.VENDORS_EDIT, Cap.BANK_ACCOUNTS_VIEW, Cap.BANK_ACCOUNTS_MANAGE,
        Cap.INVOICES_CREATE, Cap.INVOICES_SUBMIT, Cap.INVOICES_REANALYZE,
        Cap.ALERTS_ASSIGN, Cap.APPROVALS_VIEW, Cap.PAYMENTS_VIEW, Cap.PAYMENTS_SIMULATE,
        Cap.AUDIT_VIEW, Cap.ANALYTICS_VIEW, Cap.REPORTS_EXPORT,
    },
    "AP_OFFICER": _EVERYONE | {
        Cap.VENDORS_CREATE, Cap.BANK_ACCOUNTS_VIEW,
        Cap.INVOICES_CREATE, Cap.INVOICES_SUBMIT, Cap.INVOICES_REANALYZE,
    },
    "MANAGER": _EVERYONE | {
        Cap.SETTINGS_VIEW, Cap.APPROVALS_VIEW, Cap.APPROVALS_DECIDE, Cap.APPROVALS_ESCALATE,
        Cap.ANALYTICS_VIEW, Cap.REPORTS_EXPORT,
    },
    "AUDITOR": _EVERYONE | {
        Cap.SETTINGS_VIEW, Cap.BANK_ACCOUNTS_VIEW, Cap.INVOICES_REANALYZE,
        Cap.ALERTS_ASSIGN, Cap.ALERTS_RESOLVE, Cap.APPROVALS_VIEW, Cap.APPROVALS_DECIDE, Cap.PAYMENTS_VIEW,
        Cap.AUDIT_VIEW, Cap.ANALYTICS_VIEW, Cap.REPORTS_EXPORT,
    },
}


def capabilities_for(user):
    """Set of capability strings for a user. Inactive or anonymous users get none."""
    if not user or not user.is_authenticated or not user.is_active:
        return frozenset()
    return frozenset(ROLE_CAPABILITIES.get(user.role_code, ()))


def user_can(user, *capabilities):
    """True if the user has ANY of the given capabilities."""
    return bool(capabilities_for(user) & set(capabilities))
