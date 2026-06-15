from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# TEST 1: This test is correct and should PASS
def test_health_check_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# TEST 2: This test is correct and should PASS
def test_root_returns_welcome_message():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


# TEST 3: This test is INTENTIONALLY WRONG — it will fail.
# This simulates a bug: a developer made a wrong assumption
# about what the API returns.
# The actual status returned by /health is "ok",
# but this test asserts it should be "broken".
def test_health_check_wrong_assertion():
    response = client.get("/health")
    assert response.status_code == 200
    # BUG: wrong expected value on purpose
    #assert response.json()["status"] == "broken"
    assert response.json()["status"] == "ok"