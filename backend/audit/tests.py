from decimal import Decimal

from django.test import RequestFactory, TestCase

from common.test_utils import make_invoice, make_user

from .models import AuditLog, AuditLogImmutableError
from .services import log_action


class AuditLogTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.invoice = make_invoice(submitted_by=self.user)

    def test_log_action_records_entity_values_and_ip(self):
        request = RequestFactory().post("/", REMOTE_ADDR="10.0.0.7")
        entry = log_action(
            AuditLog.Action.INVOICE_UPDATED, user=self.user, entity=self.invoice,
            old_value={"amount": Decimal("100.00")}, new_value={"amount": Decimal("150.00")},
            request=request,
        )
        entry.refresh_from_db()
        self.assertEqual(entry.entity_type, "invoice")
        self.assertEqual(entry.entity_id, str(self.invoice.pk))
        self.assertEqual(entry.new_value, {"amount": "150.00"})  # Decimal serialised safely
        self.assertEqual(entry.ip_address, "10.0.0.7")

    def test_system_actions_have_no_user(self):
        entry = log_action(AuditLog.Action.FRAUD_ANALYSIS_EXECUTED, entity=self.invoice)
        self.assertIsNone(entry.user)

    def test_entries_cannot_be_modified_or_deleted(self):
        entry = log_action(AuditLog.Action.INVOICE_CREATED, user=self.user, entity=self.invoice)
        entry.description = "tampered"
        with self.assertRaises(AuditLogImmutableError):
            entry.save()
        with self.assertRaises(AuditLogImmutableError):
            entry.delete()
        with self.assertRaises(AuditLogImmutableError):
            AuditLog.objects.filter(pk=entry.pk).update(description="tampered")
        with self.assertRaises(AuditLogImmutableError):
            AuditLog.objects.all().delete()

    def test_history_survives_when_a_user_is_removed(self):
        other = make_user()
        entry = log_action(AuditLog.Action.USER_LOGIN, user=other)
        other.delete()
        entry.refresh_from_db()
        self.assertIsNone(entry.user)
