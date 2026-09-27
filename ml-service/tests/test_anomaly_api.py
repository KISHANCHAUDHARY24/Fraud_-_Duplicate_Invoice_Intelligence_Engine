"""HTTP tests for /health model status and /api/v1/fraud/anomaly."""

from services.anomaly_detector import detector

URL = "/api/v1/fraud/anomaly"
REQUEST = {
    "invoice": {"id": 1, "invoice_number": "X-1", "vendor_id": 1, "vendor_name": "ACME Corp", "amount": 13500,
                "invoice_date": "2026-09-19", "description": "Office supplies", "department": "IT",
                "submission_datetime": "2026-09-19T20:47:00Z"},     # Sunday 02:17 in Asia/Kolkata
    "vendor_context": {"vendor_invoice_count": 40, "vendor_avg_amount": 1500, "vendor_std_amount": 300,
                       "company_avg_amount": 2600, "company_std_amount": 3000, "invoices_last_30_days": 3},
}


def test_without_model_health_says_so_and_endpoint_returns_503(client, auth):
    assert client.get("/health").json()["model_loaded"] is False
    response = client.post(URL, json=REQUEST, headers=auth)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "train_model.py" in response.json()["error"]["message"]


def test_with_model(client, auth, trained_model_dir):
    assert detector.load(trained_model_dir / "models")
    health = client.get("/health").json()
    assert health["model_loaded"] is True and health["model_version"].startswith("iforest-")

    body = client.post(URL, json=REQUEST, headers=auth).json()
    assert 0 <= body["anomaly_score"] <= 1
    assert body["threshold"] == 0.6
    assert len(body["top_features"]) == 5
    assert "not proof of fraud" in body["disclaimer"]
    if body["is_anomaly"]:
        assert body["signal"]["type"] == "ML_ANOMALY"
    else:
        assert body["signal"] is None


def test_threshold_comes_from_config(client, auth, trained_model_dir):
    detector.load(trained_model_dir / "models")
    never = client.post(URL, json={**REQUEST, "config": {"ml_anomaly_threshold": 1.0}}, headers=auth).json()
    always = client.post(URL, json={**REQUEST, "config": {"ml_anomaly_threshold": 0.0}}, headers=auth).json()
    assert always["is_anomaly"] is True and always["signal"]["type"] == "ML_ANOMALY"
    assert never["threshold"] == 1.0


def test_requires_api_key(client):
    assert client.post(URL, json=REQUEST).status_code == 401
