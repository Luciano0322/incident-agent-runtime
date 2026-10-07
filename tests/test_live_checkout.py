"""Live-model scenario (proposal §15 Tier 4). Needs a running Ollama with LLM_MODEL.

Run explicitly with `pytest -m llm`; the default run deselects it.
"""

import pytest
from fastapi.testclient import TestClient

from app.agent.models import build_chat_models
from app.main import create_app
from scripts.live_smoke import CHECKOUT_INCIDENT, check_checkout_investigation

pytestmark = pytest.mark.llm


def test_real_model_investigates_the_checkout_incident(settings, database):
    app = create_app(settings, chat_models=build_chat_models(settings))

    with TestClient(app) as client:
        incident = client.post("/incidents", json=CHECKOUT_INCIDENT).json()
        response = client.post(f"/incidents/{incident['id']}/investigate")
        assert response.status_code == 200, response.text
        fetched = client.get(f"/incidents/{incident['id']}").json()

    assert check_checkout_investigation(response.json(), fetched) == []
