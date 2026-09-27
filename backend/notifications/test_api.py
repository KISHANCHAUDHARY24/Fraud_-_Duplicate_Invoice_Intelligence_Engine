from django.test import TestCase
from rest_framework.test import APIClient

from common.test_utils import make_user

from .models import Notification
from .services import notify, notify_roles


class NotificationApiTests(TestCase):
    def setUp(self):
        self.me, self.other = make_user("MANAGER"), make_user("MANAGER")
        notify([self.me], Notification.Type.APPROVAL_REQUIRED, "Approve INV-1")
        notify([self.me], Notification.Type.INVOICE_APPROVED, "INV-2 approved")
        notify([self.other], Notification.Type.APPROVAL_REQUIRED, "Not yours")
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def test_users_see_only_their_own(self):
        titles = {n["title"] for n in self.client.get("/api/notifications/").json()["results"]}
        self.assertEqual(titles, {"Approve INV-1", "INV-2 approved"})

    def test_mark_one_and_all_read(self):
        first = Notification.objects.filter(recipient=self.me).first()
        self.assertTrue(self.client.post(f"/api/notifications/{first.pk}/read/").json()["is_read"])
        self.assertEqual(self.client.get("/api/notifications/unread-count/").json(), {"unread": 1})
        self.assertEqual(self.client.post("/api/notifications/read-all/").json(), {"marked_read": 1})
        self.assertEqual(self.client.get("/api/notifications/?is_read=false").json()["count"], 0)
        self.assertEqual(Notification.objects.get(recipient=self.other).is_read, False)

    def test_cannot_mark_someone_elses_notification(self):
        theirs = Notification.objects.get(recipient=self.other)
        self.assertEqual(self.client.post(f"/api/notifications/{theirs.pk}/read/").status_code, 404)

    def test_notify_roles_skips_inactive_users_and_the_actor(self):
        auditor, inactive = make_user("AUDITOR"), make_user("AUDITOR", is_active=False)
        actor = make_user("AUDITOR")
        created = notify_roles(["AUDITOR"], Notification.Type.VENDOR_RISK_ALERT, "Bank change", exclude=actor)
        self.assertEqual({n.recipient_id for n in created}, {auditor.pk})
        self.assertFalse(Notification.objects.filter(recipient=inactive).exists())
