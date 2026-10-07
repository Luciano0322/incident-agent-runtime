import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import run_migrations

CHECKOUT_INCIDENT = {
    "title": "Checkout API latency spike",
    "description": "Checkout API latency increased significantly after 14:20.",
}


def test_create_incident_returns_201_with_created_status(client):
    response = client.post("/incidents", json=CHECKOUT_INCIDENT)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["title"] == "Checkout API latency spike"
    assert body["description"] == "Checkout API latency increased significantly after 14:20."
    assert body["status"] == "created"


def test_get_incident_returns_incident_without_report(client):
    created = client.post("/incidents", json=CHECKOUT_INCIDENT).json()

    response = client.get(f"/incidents/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["title"] == "Checkout API latency spike"
    assert body["description"] == "Checkout API latency increased significantly after 14:20."
    assert body["status"] == "created"
    assert body["latest_report"] is None


def test_get_missing_incident_returns_404(client):
    response = client.get("/incidents/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_rerunning_migrations_keeps_existing_incidents(client):
    created = client.post("/incidents", json=CHECKOUT_INCIDENT).json()

    run_migrations()

    response = client.get(f"/incidents/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Checkout API latency spike"


def test_incident_is_visible_from_a_new_application_instance(settings, client):
    created = client.post("/incidents", json=CHECKOUT_INCIDENT).json()

    with TestClient(create_app(settings)) as other_client:
        response = other_client.get(f"/incidents/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Checkout API latency spike"


def test_create_incident_strips_surrounding_whitespace(client):
    response = client.post(
        "/incidents",
        json={
            "title": "  Checkout API latency spike \n",
            "description": "\tCheckout API latency increased significantly after 14:20.  ",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Checkout API latency spike"
    assert body["description"] == "Checkout API latency increased significantly after 14:20."


@pytest.mark.parametrize("title", ["", "   ", "\n\t"])
def test_create_incident_rejects_blank_title(client, title):
    response = client.post(
        "/incidents", json={**CHECKOUT_INCIDENT, "title": title}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("description", ["", "   ", "\n\t"])
def test_create_incident_rejects_blank_description(client, description):
    response = client.post(
        "/incidents", json={**CHECKOUT_INCIDENT, "description": description}
    )

    assert response.status_code == 422
