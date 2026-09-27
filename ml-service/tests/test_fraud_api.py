"""HTTP tests for /api/v1/fraud/rules and /api/v1/vendor/analyze."""

RULES_URL = "/api/v1/fraud/rules"
VENDOR_URL = "/api/v1/vendor/analyze"

INVOICE = {"id": 100, "invoice_number": "INV-2001", "vendor_id": 4, "vendor_name": "ACME Corp", "amount": 9800,
           "invoice_date": "2026-09-04", "description": "Office computer equipment", "department": "IT",
           "submission_datetime": "2026-09-19T20:47:00Z"}   # = Sunday 02:17 in Asia/Kolkata
RECENT = [
    {"id": 1, "invoice_number": "INV-1", "vendor_name": "ACME Corp", "amount": 9900, "invoice_date": "2026-09-01",
     "description": "Office computer equipment", "department": "IT"},
    {"id": 2, "invoice_number": "INV-2", "vendor_name": "ACME Corp", "amount": 9700, "invoice_date": "2026-09-03",
     "description": "Office computer equipment", "department": "IT"},
]


def test_rules_endpoint(client, auth):
    response = client.post(RULES_URL, json={"invoice": INVOICE, "recent_vendor_invoices": RECENT}, headers=auth)
    assert response.status_code == 200, response.json()
    body = response.json()
    types = {signal["type"] for signal in body["signals"]}
    assert types == {"TIME_ANOMALY", "THRESHOLD_PROXIMITY", "SPLIT_PURCHASE"}
    assert body["routing_hints"] == {"above_approval_threshold": False}
    assert body["features"]["is_weekend"] == 1.0
    assert "not a determination of fraud" in body["disclaimer"]


def test_settings_from_django_change_the_result(client, auth):
    config = {"timezone": "UTC", "working_days": [0, 1, 2, 3, 4, 5, 6], "working_hours": {"start": "00:00", "end": "23:59"},
              "approval_threshold": 50000}
    body = client.post(RULES_URL, json={"invoice": INVOICE, "recent_vendor_invoices": RECENT, "config": config},
                       headers=auth).json()
    assert body["signals"] == []   # always-open company, much higher threshold: nothing unusual
    assert body["features"]["threshold_distance"] > 0.8


def test_rules_require_api_key(client):
    assert client.post(RULES_URL, json={"invoice": INVOICE}).status_code == 401


def test_naive_datetime_is_rejected(client, auth):
    bad = {**INVOICE, "submission_datetime": "2026-09-19T20:47:00"}
    response = client.post(RULES_URL, json={"invoice": bad}, headers=auth)
    assert response.status_code == 422
    assert "timezone" in response.json()["error"]["message"]


def test_invalid_config_is_rejected(client, auth):
    for config in ({"timezone": "Mars/Base"}, {"working_hours": {"start": "19:00", "end": "08:00"}},
                   {"working_days": [9]}, {"approval_threshold": 0}):
        response = client.post(RULES_URL, json={"invoice": INVOICE, "config": config}, headers=auth)
        assert response.status_code == 422, config


def test_vendor_analyze(client, auth):
    body = client.post(VENDOR_URL, json={
        "vendor_id": 4, "vendor_name": "ACME Corp",
        "bank": {"current_account_masked": "****4821", "current_account_age_days": 5, "previous_account_masked": "****1111"},
        "recent_invoices": RECENT + [{**RECENT[0], "id": 3, "invoice_number": "INV-3", "invoice_date": "2026-09-04"}],
        "vendor_context": {"open_alert_count": 1},
    }, headers=auth).json()
    types = [indicator["type"] for indicator in body["indicators"]]
    assert types[0] == "BANK_ACCOUNT_CHANGE"   # strongest first
    assert set(types) == {"BANK_ACCOUNT_CHANGE", "VENDOR_ANOMALY", "THRESHOLD_PROXIMITY", "SPLIT_PURCHASE"}
    assert body["indicator_count"] == 4


def test_vendor_analyze_clean_vendor(client, auth):
    body = client.post(VENDOR_URL, json={"vendor_name": "Quiet Supplies Ltd"}, headers=auth).json()
    assert body["indicators"] == [] and body["indicator_count"] == 0
