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
    # assert response.json()["status"] == "broken"


# TEST 4 : This test is correct and should pass.
def test_version_returns_1_0_0():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == "1.0.102"


# TEST 5 : This test is correct and should pass.
def test_version_returns_development():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["environment"] == "development"


# TEST 6 : This one has an intentional bug.
def test_about_endpoint():
    response = client.get("/about")
    assert response.status_code == 200
    # Fixed: the correct key is "name", not "title"
    assert "name" in response.json()
    assert response.json()["name"] == "DevOps Lab API"


def test_intentionally_broken():
    response = client.get("/health")
    assert response.json()["status"] == "this will never match 3"
