import pytest
from app import app

@pytest.fixture
def client():
    """
    Sets up a test client for the Flask application.
    """
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
