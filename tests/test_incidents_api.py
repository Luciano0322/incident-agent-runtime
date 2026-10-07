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
