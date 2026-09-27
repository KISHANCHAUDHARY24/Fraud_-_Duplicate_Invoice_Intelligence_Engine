"""HTTP-level tests: health, authentication, validation errors, duplicate endpoint."""

URL = "/api/v1/duplicate/check"

ORIGINAL = {"id": 12, "invoice_number": "INV-1001", "vendor_id": 4, "vendor_name": "ACME Corp",
            "amount": 5000, "invoice_date": "2026-09-01", "description": "Software License"}


def payload(**invoice_overrides):
    return {"invoice": {**ORIGINAL, "id": 50, "invoice_number": "INV1001", "invoice_date": "2026-09-03",
                        **invoice_overrides},
            "candidates": [ORIGINAL]}


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_swagger_docs_available(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert URL in schema["paths"]


def test_missing_api_key_is_rejected(client):
    response = client.post(URL, json=payload())
    assert response.status_code == 401
    assert response.json() == {"success": False, "error": {
        "code": "NOT_AUTHENTICATED", "message": "Missing or invalid internal API key.", "details": None}}


def test_wrong_api_key_is_rejected(client):
    assert client.post(URL, json=payload(), headers={"X-Internal-API-Key": "guess"}).status_code == 401


def test_duplicate_check_success(client, auth):
    response = client.post(URL, json=payload(), headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["is_possible_duplicate"] is True
    assert body["duplicate_score"] >= 95
    assert body["matched_invoice_number"] == "INV-1001"
    assert "Same vendor" in body["signals"]


def test_invalid_input_returns_readable_422(client, auth):
    response = client.post(URL, json=payload(amount=-5, currency="dollars"), headers=auth)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    fields = {item["field"] for item in error["details"]}
    assert fields == {"invoice.amount", "invoice.currency"}
    assert error["message"].startswith("invoice.")


def test_missing_required_field(client, auth):
    body = payload()
    del body["invoice"]["invoice_date"]
    response = client.post(URL, json=body, headers=auth)
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "invoice.invoice_date", "message": "Field required"}]


def test_bad_weights_are_rejected(client, auth):
    body = payload()
    body["weights"] = {"invoice_number": 0.9, "vendor": 0.9, "amount": 0, "date": 0, "description": 0}
    response = client.post(URL, json=body, headers=auth)
    assert response.status_code == 422
    assert "add up to 1.0" in response.json()["error"]["message"]


def test_unknown_route_uses_error_format(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
