def test_unauthorized_access(client):
    response = client.post("/api/safety/incidents/")
    assert response.status_code == 401