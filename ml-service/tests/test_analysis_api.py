"""
POST /api/v1/fraud/analyze with the 5 demo scenarios (docs/testing.md §5),
and POST /api/v1/risk/score. The config is Django's real default settings.
"""

import importlib.util
from pathlib import Path

import pytest

from services.anomaly_detector import detector

ANALYZE = "/api/v1/fraud/analyze"
SCORE = "/api/v1/risk/score"


def _django_defaults():
    path = Path(__file__).resolve().parents[2] / "backend" / "system_settings" / "defaults.py"
    spec = importlib.util.spec_from_file_location("django_defaults", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {key: value for key, (value, _, _) in module.DEFAULT_SETTINGS.items()}


DJANGO_CONFIG = _django_defaults()
VENDOR = {"vendor_invoice_count": 40, "vendor_avg_amount": 1500, "vendor_std_amount": 300, "company_avg_amount": 2600,
          "company_std_amount": 3000, "invoices_last_30_days": 3, "avg_monthly_invoices": 3,
          "days_since_previous_invoice": 9, "vendor_age_days": 500}
BASE = {"id": 900, "invoice_number": "AC-2201", "vendor_id": 4, "vendor_name": "ACME Corp", "amount": 1480.0,
        "invoice_date": "2026-09-14", "description": "Office supplies", "department": "IT",
        "submission_datetime": "2026-09-15T11:20:00+05:30"}


def history(invoice_id, amount, invoice_date, description="Office computer equipment", number=None):
    return {"id": invoice_id, "invoice_number": number or f"AC-{invoice_id}", "vendor_id": 4, "vendor_name": "ACME Corp",
            "amount": amount, "invoice_date": invoice_date, "description": description, "department": "IT"}


SCENARIOS = {
    "normal": {},
    "duplicate": {"invoice": {"invoice_number": "INV1001", "amount": 5000.0, "invoice_date": "2026-09-03",
                              "description": "Software licence"},
                  "duplicate_candidates": [history(12, 5000.0, "2026-09-01", "Software License", "INV-1001")]},
    "unusual": {"invoice": {"amount": 13500.0, "submission_datetime": "2026-09-20T02:17:00+05:30"}},
    "split": {"invoice": {"amount": 9800.0, "invoice_date": "2026-09-04", "description": "Office computer equipment"},
              "recent_vendor_invoices": [history(1, 9900.0, "2026-09-01"), history(2, 9700.0, "2026-09-03")]},
    "bank_change": {"bank": {"current_account_masked": "****4821", "current_account_age_days": 12,
                             "previous_account_masked": "****1111"}},
}


def request_for(name):
    scenario = SCENARIOS[name]
    body = {"invoice": {**BASE, **scenario.get("invoice", {})}, "vendor_context": VENDOR, "config": DJANGO_CONFIG}
    body.update({k: v for k, v in scenario.items() if k != "invoice"})
    return body


# Expected level WITHOUT the ML model (rules + duplicates only) and a signal that must be present.
# Note "unusual": rules alone give 15 + 10 = 25 points. Until Phase 16 that was LOW (auto-approvable); the
# extreme-amount floor (amount >= 6 sigma above the vendor's average) now lifts it to MEDIUM even without the model.
# Django still never auto-approves when the ML part was skipped (Phase 9 fail-safe).
EXPECTED = {
    "normal": ("LOW", None),
    "duplicate": ("HIGH", "DUPLICATE"),
    "unusual": ("MEDIUM", "AMOUNT_ANOMALY"),
    "split": ("MEDIUM", "SPLIT_PURCHASE"),
    "bank_change": ("HIGH", "BANK_ACCOUNT_CHANGE"),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_demo_scenarios_without_model(client, auth, name):
    body = client.post(ANALYZE, json=request_for(name), headers=auth).json()
    level, must_have = EXPECTED[name]
    assert body["risk_level"] == level, body["explanation"]
    types = [signal["type"] for signal in body["signals"]]
    if must_have:
        assert must_have in types
    assert "ML_ANOMALY" not in types
    assert body["anomaly"]["model_loaded"] is False
    assert any("ML model not loaded" in w for w in body["warnings"])


@pytest.mark.parametrize("name", SCENARIOS)
def test_demo_scenarios_with_model(client, auth, trained_model_dir, name):
    detector.load(trained_model_dir / "models")
    body = client.post(ANALYZE, json=request_for(name), headers=auth).json()
    level, _ = EXPECTED[name]
    order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    # The ML signal can only ADD points, so the level is at least the rules-only level.
    assert order.index(body["risk_level"]) >= order.index(level)
    assert body["anomaly"]["model_loaded"] is True and body["warnings"] == []
    if name == "normal":
        assert body["risk_level"] == "LOW"
    if name == "unusual":
        assert body["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
        assert "ML_ANOMALY" in [s["type"] for s in body["signals"]]


def test_response_is_explainable_and_consistent(client, auth):
    body = client.post(ANALYZE, json=request_for("unusual"), headers=auth).json()
    breakdown, floor = body["scoring"]["breakdown"], body["scoring"]["floor_applied"]
    points = sum(item["points"] for item in breakdown)
    if floor is None:
        assert points == body["risk_score"]                                          # reasons add up...
    else:                                                                            # ...or a floor says why not
        assert body["risk_score"] == max(points, floor["min_score"])
        assert body["explanation"][-1].startswith(f"Minimum score {floor['min_score']}")
    point_lines = [line for line in body["explanation"] if " (+" in line]
    assert [line.split(" (+")[0] for line in point_lines] == [item["message"] for item in breakdown]
    assert [s["type"] for s in body["signals"]] == [item["type"] for item in breakdown]   # same order
    assert "not a determination of fraud" in body["summary"]
    assert set(body["features"]) >= {"log_amount", "is_weekend", "duplicate_similarity"}


def test_duplicate_details_are_attached(client, auth):
    body = client.post(ANALYZE, json=request_for("duplicate"), headers=auth).json()
    duplicate_signal = next(s for s in body["signals"] if s["type"] == "DUPLICATE")
    assert duplicate_signal["related_invoice_id"] == 12
    assert "Same vendor" in duplicate_signal["details"]["reasons"]
    assert body["duplicate"]["matched_invoice_number"] == "INV-1001"
    assert body["scoring"]["floor_applied"]["signal_type"] == "DUPLICATE"


def test_settings_change_the_outcome(client, auth):
    relaxed = {**DJANGO_CONFIG, "signal_floors": {}, "signal_weights": {**DJANGO_CONFIG["signal_weights"], "BANK_ACCOUNT_CHANGE": 5}}
    body = client.post(ANALYZE, json={**request_for("bank_change"), "config": relaxed}, headers=auth).json()
    assert (body["risk_score"], body["risk_level"]) == (5, "LOW")


def test_routing_hint(client, auth):
    body = client.post(ANALYZE, json={**request_for("normal"), "invoice": {**BASE, "amount": 12000.0}}, headers=auth).json()
    assert body["routing_hints"]["above_approval_threshold"] is True


def test_analyze_validation_and_auth(client, auth):
    assert client.post(ANALYZE, json=request_for("normal")).status_code == 401
    bad = request_for("normal")
    bad["config"] = {**DJANGO_CONFIG, "risk_level_thresholds": {"medium": 90, "high": 50, "critical": 95}}
    response = client.post(ANALYZE, json=bad, headers=auth)
    assert response.status_code == 422
    assert "increase" in response.json()["error"]["message"]


def test_risk_score_endpoint(client, auth):
    body = client.post(SCORE, json={"signals": [
        {"type": "DUPLICATE", "strength": 0.94, "message": "94% similarity with invoice INV-1001"},
        {"type": "BANK_ACCOUNT_CHANGE", "strength": 1.0},
    ]}, headers=auth).json()
    assert (body["risk_score"], body["risk_level"]) == (60, "HIGH")      # 28 + 20 = 48, floor 60
    assert body["explanation"][0] == "94% similarity with invoice INV-1001 (+28)"
    assert body["floor_applied"]["signal_type"] in ("DUPLICATE", "BANK_ACCOUNT_CHANGE")


def test_risk_score_rejects_bad_input(client, auth):
    response = client.post(SCORE, json={"signals": [{"type": "MADE_UP", "strength": 2}]}, headers=auth)
    assert response.status_code == 422
    assert {d["field"] for d in response.json()["error"]["details"]} == {"signals.0.type", "signals.0.strength"}
