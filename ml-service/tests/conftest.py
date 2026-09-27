import os

# Must be set before config.get_settings() runs. load_dotenv() never overrides an
# existing variable, so tests use this key instead of the real one in .env.
os.environ["INTERNAL_API_KEY"] = "test-internal-key"
# Tests never use the real trained model in ml-service/models. Tests that need a model
# train a small one in a temporary folder (see the `trained_model_dir` fixture).
os.environ["MODEL_DIR"] = os.path.join(os.path.dirname(__file__), "_no_model_here")

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import get_settings  # noqa: E402
from main import app  # noqa: E402
from services.anomaly_detector import detector  # noqa: E402
from training import dataset, train  # noqa: E402

API_KEY_HEADER = {"X-Internal-API-Key": "test-internal-key"}


@pytest.fixture
def client():
    get_settings.cache_clear()
    with TestClient(app) as test_client:  # "with" runs the startup/shutdown (lifespan) code
        yield test_client
    detector.model = detector.scaler = detector.metadata = None   # never leak a loaded model between tests


@pytest.fixture(scope="session")
def small_tables():
    """A small synthetic dataset (fast), generated once per test run."""
    return dataset.generate(n_vendors=15, start=date(2025, 1, 1), months=10, seed=7)


@pytest.fixture(scope="session")
def trained_model_dir(small_tables, tmp_path_factory):
    root = tmp_path_factory.mktemp("ml")
    dataset.save(small_tables, root / "raw")
    train.run(root / "raw", root / "models", root / "reports", log=lambda *_: None)
    return root


@pytest.fixture
def auth():
    return API_KEY_HEADER
