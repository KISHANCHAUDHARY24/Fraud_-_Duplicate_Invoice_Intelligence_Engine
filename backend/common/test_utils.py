"""Factories shared by tests in every app."""

import itertools
from datetime import date, timedelta
from decimal import Decimal

from accounts.models import Role, User
from invoices.models import Invoice
from vendors.models import Vendor

_counter = itertools.count(1)


def make_user(role_code=Role.Code.AP_OFFICER, **fields):
    n = next(_counter)
    fields.setdefault("username", f"user{n}")
    fields.setdefault("email", f"user{n}@example.com")
    password = fields.pop("password", "Str0ng!Passw0rd")
    return User.objects.create_user(role=Role.objects.get(code=role_code), password=password, **fields)


def make_vendor(**fields):
    fields.setdefault("vendor_name", f"Vendor {next(_counter)} Ltd")
    return Vendor.objects.create(**fields)


def fake_analysis(level="LOW", score=0, signals=(), model_loaded=True, duplicate=None):
    """
    A response shaped exactly like POST /api/v1/fraud/analyze, for tests that must not
    depend on the ML service. `signals` is a list of (type, points, message[, related_invoice_id]).
    """
    signal_rows = [
        {"type": s[0], "strength": 1.0, "severity": "HIGH" if s[1] >= 20 else "MEDIUM", "message": s[2],
         "details": {}, "related_invoice_id": s[3] if len(s) > 3 else None}
        for s in signals
    ]
    return {
        "invoice_id": None, "risk_score": score, "risk_level": level,
        "summary": f"Risk score {score}/100 ({level}). This is a risk indicator for human review, not a determination of fraud.",
        "explanation": [f"{s[2]} (+{s[1]})" for s in signals],
        "signals": signal_rows,
        "scoring": {"risk_score": score, "risk_level": level, "points_total": sum(s[1] for s in signals),
                    "capped": False, "floor_applied": None,
                    "breakdown": [{"type": s[0], "strength": 1.0, "weight": s[1], "points": s[1], "message": s[2]}
                                  for s in signals],
                    "explanation": [], "summary": ""},
        "duplicate": duplicate or {"duplicate_score": 0, "is_possible_duplicate": False, "matched_invoice_id": None,
                                   "matched_invoice_number": None, "components": None, "reasons": [], "candidates": []},
        "anomaly": {"model_loaded": model_loaded, "model_version": "iforest-test" if model_loaded else None,
                    "anomaly_score": 0.1 if model_loaded else None, "is_anomaly": False,
                    "threshold": 0.6, "reasons": []},
        "features": {}, "routing_hints": {"above_approval_threshold": False},
        "warnings": [] if model_loaded else ["ML model not loaded: the anomaly signal was skipped."],
        "analyzed_at": "2026-09-24T10:00:00Z",
    }


def make_invoice(vendor=None, submitted_by=None, **fields):
    fields.setdefault("invoice_number", f"INV-{next(_counter):05d}")
    fields.setdefault("invoice_date", date.today() - timedelta(days=5))
    fields.setdefault("amount", Decimal("1250.00"))
    fields.setdefault("description", "Office supplies")
    return Invoice.objects.create(
        vendor=vendor or make_vendor(),
        submitted_by=submitted_by or make_user(),
        **fields,
    )
