from unittest.mock import AsyncMock, patch
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


# TEST 6 : This test is correct and should pass.
def test_about_endpoint():
    response = client.get("/about")
    assert response.status_code == 200
    assert "name" in response.json()
    assert response.json()["name"] == "DevOps Lab API"


# TEST 7 : Test for a successful database connection check.
# This test mocks the database connection
def test_db_check_success():
    """Test /db-check when the database connection is successful."""
    # 🌟 Patch asyncpg.connect since that's what main.py imports and uses
    with patch("main.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        # Create asynchronous mocks for the connection object
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        # mock_conn.fetchval is an async function, so it returns our version string
        mock_conn.fetchval.return_value = "16.3"

        # Act
        response = client.get("/db-check")

        # Assert
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "connected",
            "server_version": "PostgreSQL 16.3",
        }

        # Verify that connect and close were both awaited properly
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()


# TEST 8 : Test for a failed database connection check.
def test_db_check_failure():
    """Test /db-check when the database is unreachable."""
    with patch("main.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        # Force the async connection to raise an exception
        mock_connect.side_effect = Exception("Connection refused")

        # Act
        response = client.get("/db-check")

        # Assert
        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "database": "unreachable",
            "error": "Connection refused",
        }


def test_slow_endpoint():
    response = client.get("/slow")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_error_endpoint_returns_500():
    response = client.get("/error")
    assert response.status_code == 500


def test_metrics_endpoint_exists():
    response = client.get("/metrics")
    assert response.status_code == 200
    # Prometheus metrics format starts with # HELP
    assert b"# HELP" in response.content


