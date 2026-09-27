"""
Build the demo: accounts, vendors, a year of normal history and the five demo scenarios
(docs/testing.md §5). Scenarios go through the real workflow (approvals.services.submit_invoice →
Django → FastAPI → trained model → routing), so what you see in the UI is what the system decided.

Everything is idempotent: running it again tops up what is missing and never duplicates records.
"""

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from approvals import services as workflow
from approvals.models import Approval, Payment
from fraud.models import FraudAnalysis
from invoices.models import Invoice
from notifications.models import Notification
from system_settings.services import get_setting
from vendors.models import Vendor, VendorBankAccount
from vendors.services import add_bank_account

from .data import DEMO_EMAIL_DOMAIN, DEMO_REG_PREFIX, HISTORY_MONTHS, HISTORY_PER_MONTH, USERS, VENDORS

Status = Invoice.ApprovalStatus
BASELINE_NOTE = "Baseline record created by seed_data for historical demo data; not a live model analysis."


class DemoConflict(Exception):
    """A non-demo account already uses a demo username."""


# ---------------------------------------------------------------------------------------------
# time helpers (business timezone)
# ---------------------------------------------------------------------------------------------
def business_zone():
    return ZoneInfo(get_setting("timezone"))


def at(day: date, hour: int, minute: int, zone) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=zone)


def last_weekday_before(day: date) -> date:
    """The most recent Monday–Friday strictly before `day` (so demo submissions are never in the future)."""
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def last_sunday_before(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def weekdays_before(day: date, count: int) -> date:
    """`count` working days (Mon–Fri) before `day`."""
    for _ in range(count):
        day = last_weekday_before(day)
    return day


def next_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


# ---------------------------------------------------------------------------------------------
# accounts and vendors
# ---------------------------------------------------------------------------------------------
def ensure_users(password) -> dict:
    """{role: user}. Demo accounts get `password` on every run; real accounts are never touched."""
    conflicts = [u.username for u in User.objects.filter(username__in=[d.username for d in USERS])
                 if not u.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")]
    if conflicts:
        raise DemoConflict(f"These usernames belong to non-demo accounts: {', '.join(conflicts)}. "
                           "Rename them or use a fresh database.")
    users = {}
    for demo in USERS:
        user, _ = User.objects.update_or_create(username=demo.username, defaults={
            "email": f"{demo.username}@{DEMO_EMAIL_DOMAIN}", "first_name": demo.first_name, "last_name": demo.last_name,
            "department": demo.department, "role": Role.objects.get(code=demo.role), "is_active": True})
        user.set_password(password)
        user.save()
        users[demo.role] = user
    return users


def ensure_vendors(admin, today) -> dict:
    """{code: vendor}, each with an active bank account valid for the whole history."""
    vendors = {}
    for index, demo in enumerate(VENDORS):
        vendor, created = Vendor.objects.get_or_create(registration_number=f"{DEMO_REG_PREFIX}{demo.code}", defaults={
            "vendor_name": demo.name, "email": f"billing@{demo.code.lower()}.{DEMO_EMAIL_DOMAIN}",
            "phone": f"+91 22 5550 {1000 + index}", "address": f"{10 + index} Demo Business Park, Mumbai"})
        if created or not vendor.bank_accounts.exists():
            account = add_bank_account(vendor, demo.bank, f"5010{index:02d}{734215 + 9173 * index}", user=admin)
            VendorBankAccount.objects.filter(pk=account.pk).update(valid_from=today - timedelta(days=30 * (HISTORY_MONTHS + 2)))
        vendors[demo.code] = vendor
    return vendors


# ---------------------------------------------------------------------------------------------
# history: a year of normal, already decided invoices
# ---------------------------------------------------------------------------------------------
def seed_history(users, vendors, today, zone, rng) -> int:
    """Created directly (not analysed live): background for charts and for the model's vendor statistics."""
    if Invoice.objects.filter(invoice_number=f"{VENDORS[0].code}-1001", vendor=vendors[VENDORS[0].code]).exists():
        return 0
    ap, manager = users["AP_OFFICER"], users["MANAGER"]
    threshold = Decimal(str(get_setting("approval_threshold")))
    created = 0
    with transaction.atomic():
        for demo in VENDORS:
            vendor = vendors[demo.code]
            account = vendor.active_bank_account
            number = 1000
            for months_back in range(HISTORY_MONTHS, 0, -1):
                for slot in range(HISTORY_PER_MONTH):
                    number += 1
                    invoice_day = today - timedelta(days=30 * months_back - 12 * slot + rng.randint(0, 8))
                    submitted = at(next_weekday(invoice_day + timedelta(days=rng.randint(1, 3))),
                                   rng.randint(9, 16), rng.randint(0, 59), zone)
                    amount = Decimal(str(round(demo.typical_amount * rng.uniform(0.8, 1.2), 2)))
                    rejected = rng.random() < 0.07
                    score = rng.randint(0, 22)
                    invoice = Invoice.objects.create(
                        invoice_number=f"{demo.code}-{number}", vendor=vendor, invoice_date=invoice_day,
                        due_date=invoice_day + timedelta(days=30), submission_date=submitted, amount=amount,
                        description=demo.description, purchase_category=demo.category, department=demo.department,
                        submitted_by=ap, payment_bank_account=account,
                        approval_status=Status.REJECTED if rejected else Status.APPROVED,
                        fraud_status=Invoice.FraudStatus.NO_ISSUES, risk_score=score, risk_level="LOW")
                    analysis = FraudAnalysis.objects.create(
                        invoice=invoice, risk_score=score, risk_level="LOW", model_version="seed-baseline", raw_response={
                            "summary": f"Risk score {score}/100 (LOW). This is a risk indicator for human review, "
                                       "not a determination of fraud.",
                            "explanation": [], "warnings": [BASELINE_NOTE]})
                    FraudAnalysis.objects.filter(pk=analysis.pk).update(analyzed_at=submitted + timedelta(seconds=40))
                    # Small amounts were approved automatically; larger ones and rejections by the manager.
                    automatic = not rejected and amount <= threshold and rng.random() < 0.7
                    decided = submitted + (timedelta(seconds=45) if automatic else timedelta(hours=rng.randint(2, 30)))
                    approval = Approval.objects.create(
                        invoice=invoice, level=Approval.Level.STANDARD if automatic else Approval.Level.MANAGER,
                        assigned_to=None if automatic else manager, decided_by=None if automatic else manager,
                        decision=Approval.Decision.REJECTED if rejected else Approval.Decision.APPROVED,
                        comment="Purchase order missing" if rejected else "")
                    # created_at / decided_at are set explicitly so "time to decide" is consistent.
                    Approval.objects.filter(pk=approval.pk).update(created_at=submitted + timedelta(seconds=41),
                                                                   decided_at=decided)
                    created += 1
    return created


# ---------------------------------------------------------------------------------------------
# the five demo scenarios
# ---------------------------------------------------------------------------------------------
@dataclass
class ScenarioResult:
    number: int
    title: str
    expected: str
    invoice: Invoice = None
    ok: bool = None
    notes: list = field(default_factory=list)

    @property
    def outcome(self):
        if self.invoice is None:
            return "not run"
        invoice = self.invoice
        if invoice.approval_status == Status.DRAFT:
            return "draft (not analysed yet)"
        pending = invoice.approvals.filter(decision=Approval.Decision.PENDING).first()
        route = f" -> {pending.get_level_display()}" if pending else ""
        return f"{invoice.risk_score} {invoice.risk_level} {invoice.get_approval_status_display()}{route}"


def _draft(vendor, number, ap, amount, invoice_day, description, category, department, account=None):
    invoice, _ = Invoice.objects.get_or_create(vendor=vendor, invoice_number=number, defaults={
        "invoice_date": invoice_day, "due_date": invoice_day + timedelta(days=30), "amount": Decimal(amount),
        "description": description, "purchase_category": category, "department": department, "submitted_by": ap,
        "payment_bank_account": account or vendor.active_bank_account})
    return invoice


def _submit(invoice, ap, submitted_at):
    """Submit a draft through the real workflow; an already submitted invoice is left as it is."""
    if invoice.approval_status == Status.DRAFT:
        invoice = workflow.submit_invoice(invoice, ap, submitted_at=submitted_at)
    invoice.refresh_from_db()
    return invoice


def run_scenarios(users, vendors, today, zone, analyse=True) -> list:
    """With analyse=False (ML service down) the scenario invoices are only created as drafts."""
    ap, admin = users["AP_OFFICER"], users["ADMIN"]
    base_day = last_weekday_before(today)
    base = at(base_day, 11, 20, zone)                  # a normal weekday, office hours
    submit = (lambda invoice, when: _submit(invoice, ap, when)) if analyse else (lambda invoice, when: invoice)
    meta = {demo.code: demo for demo in VENDORS}
    results = []

    # 1. Normal invoice: expected LOW and approved automatically; then a simulated payment.
    ev = meta["EV"]
    result = ScenarioResult(1, "Normal invoice", "LOW, approved automatically, then paid (simulated)")
    invoice = submit(_draft(vendors["EV"], "EV-2001", ap, "690.00", base_day - timedelta(days=1), ev.description,
                            ev.category, ev.department), base)
    if invoice.approval_status == Status.APPROVED:
        workflow.simulate_payment(invoice, admin)
        invoice.refresh_from_db()
    result.invoice, result.ok = invoice, invoice.risk_level == "LOW" and invoice.approval_status in (Status.APPROVED, Status.PAID)
    results.append(result)

    # 2. Duplicate: INV-1001 was paid three days earlier; INV1001 (no dash) arrives with the same amount.
    cs = meta["CS"]
    result = ScenarioResult(2, "Duplicate invoice", "Possible duplicate of INV-1001, HIGH or CRITICAL, auditor review")
    earlier = weekdays_before(base_day, 3)
    submit(_draft(vendors["CS"], "INV-1001", ap, "5000.00", earlier - timedelta(days=2), "Software License",
                  cs.category, cs.department), at(earlier, 10, 5, zone))
    invoice = submit(_draft(vendors["CS"], "INV1001", ap, "5000.00", base_day - timedelta(days=2), "Software licence",
                            cs.category, cs.department), base)
    result.invoice = invoice
    result.ok = invoice.risk_level in ("HIGH", "CRITICAL") and invoice.signals.filter(signal_type="DUPLICATE").exists()
    results.append(result)

    # 3. Unusual: Sunday 02:17, about 9x the vendor's usual amount.
    ac = meta["AC"]
    result = ScenarioResult(3, "Unusual invoice", "Time + amount + ML signals, MEDIUM or higher, reviewer")
    sunday = last_sunday_before(today)
    invoice = submit(_draft(vendors["AC"], "AC-2003", ap, "13500.00", sunday - timedelta(days=1), ac.description,
                            ac.category, ac.department), at(sunday, 2, 17, zone))
    types = set(invoice.signals.values_list("signal_type", flat=True))
    result.invoice = invoice
    result.ok = {"TIME_ANOMALY", "AMOUNT_ANOMALY"} <= types and invoice.risk_level in ("MEDIUM", "HIGH", "CRITICAL")
    results.append(result)

    # 4. Split purchase: three invoices just under the 10,000 threshold within four days.
    bp = meta["BP"]
    result = ScenarioResult(4, "Split purchase", "Potential split purchase, MEDIUM or higher, reviewer")
    for back, (number, amount) in zip((3, 1, 0), (("BP-3001", "9900.00"), ("BP-3002", "9700.00"), ("BP-3003", "9800.00"))):
        day = weekdays_before(base_day, back)
        invoice = submit(_draft(vendors["BP"], number, ap, amount, day - timedelta(days=1),
                                "Consulting - phase 2", bp.category, bp.department), at(day, 11, 20, zone))
    result.invoice = invoice
    result.ok = (invoice.signals.filter(signal_type="SPLIT_PURCHASE").exists()
                 and invoice.risk_level in ("MEDIUM", "HIGH", "CRITICAL"))
    results.append(result)

    # 5. Bank account change: the vendor's account changed yesterday, then an invoice arrives.
    fl = meta["FL"]
    result = ScenarioResult(5, "Bank account change", "Bank account change signal, HIGH or higher, auditor review")
    vendor = vendors["FL"]
    if vendor.bank_accounts.count() < 2:
        account = add_bank_account(vendor, "Federal Bank", "998877665544", user=admin)
        VendorBankAccount.objects.filter(pk=account.pk).update(valid_from=base_day - timedelta(days=1))
    invoice = submit(_draft(vendor, "FL-2005", ap, "3350.00", base_day - timedelta(days=1), fl.description,
                            fl.category, fl.department, account=vendor.active_bank_account), base)
    result.invoice = invoice
    result.ok = (invoice.signals.filter(signal_type="BANK_ACCOUNT_CHANGE").exists()
                 and invoice.risk_level in ("HIGH", "CRITICAL"))
    results.append(result)

    # Two drafts, so the AP officer has something to edit and submit during a demo.
    for code, number, amount in (("DF", "DF-2101", "2550.00"), ("GM", "GM-2101", "5100.00")):
        demo = meta[code]
        _draft(vendors[code], number, ap, amount, base_day, demo.description, demo.category, demo.department)

    if not analyse:
        for result in results:
            result.ok = None
    return results


# ---------------------------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------------------------
def demo_counts():
    vendors = Vendor.objects.filter(registration_number__startswith=DEMO_REG_PREFIX)
    return {"vendors": vendors.count(), "invoices": Invoice.objects.filter(vendor__in=vendors).count(),
            "users": User.objects.filter(email__endswith=f"@{DEMO_EMAIL_DOMAIN}").count()}


@transaction.atomic
def reset_demo():
    """Remove demo business data (invoices of demo vendors, then the vendors). Demo users are kept,
    their notifications cleared; audit entries stay (the audit log is append-only)."""
    vendors = Vendor.objects.filter(registration_number__startswith=DEMO_REG_PREFIX)
    invoices = Invoice.objects.filter(vendor__in=vendors)
    counts = {"invoices": invoices.count(), "vendors": vendors.count()}
    # Payments protect their invoice (financial records must not vanish by accident), so the demo's
    # simulated payments are removed explicitly first.
    Payment.objects.filter(invoice__in=invoices).delete()
    invoices.delete()          # cascades to analyses, signals, alerts, approvals, items
    vendors.delete()           # cascades to their bank accounts
    Notification.objects.filter(recipient__email__endswith=f"@{DEMO_EMAIL_DOMAIN}").delete()
    return counts


def business_today(zone):
    return timezone.localtime(timezone.now(), zone).date()


def make_rng():
    return random.Random(42)   # same history every time
