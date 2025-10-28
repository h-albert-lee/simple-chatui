"""Tests for the multi-user authentication system."""

import pytest
from fastapi.testclient import TestClient
from chatbot.core import storage
from chatbot.backend.api import router
from fastapi import FastAPI


@pytest.fixture(autouse=True)
def init_database():
    """Initialize database for all tests."""
    storage.initialize_database()


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user and return credentials."""
    username = "testuser"
    password = "testpass123"
    
    # Clean up any existing user
    try:
        storage.delete_user_by_username(username)
    except:
        pass
    
    user_id = storage.create_user(username, password)
    return {"username": username, "password": password, "user_id": user_id}


def test_user_signup_success(client):
    """Test successful user signup."""
    import uuid
    username = f"newuser_{uuid.uuid4().hex[:8]}"
    response = client.post("/api/v1/auth/signup", json={
        "username": username,
        "password": "newpass123"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["username"] == username
    assert "token" in data
    assert len(data["token"]) > 0


def test_user_signup_duplicate_username(client, test_user):
    """Test signup with duplicate username."""
    response = client.post("/api/v1/auth/signup", json={
        "username": test_user["username"],
        "password": "differentpass"
    })
    
    assert response.status_code == 409
    assert "already taken" in response.json()["detail"].lower()


def test_user_login_success(client, test_user):
    """Test successful user login."""
    response = client.post("/api/v1/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == test_user["user_id"]
    assert data["username"] == test_user["username"]
    assert "token" in data
    assert len(data["token"]) > 0


def test_user_login_invalid_credentials(client, test_user):
    """Test login with invalid credentials."""
    # Wrong password
    response = client.post("/api/v1/auth/login", json={
        "username": test_user["username"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    
    # Wrong username
    response = client.post("/api/v1/auth/login", json={
        "username": "nonexistentuser",
        "password": test_user["password"]
    })
    assert response.status_code == 401


def test_user_logout_success(client, test_user):
    """Test successful user logout."""
    # First login to get a token
    login_response = client.post("/api/v1/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })
    token = login_response.json()["token"]
    
    # Then logout
    response = client.post("/api/v1/auth/logout", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 204


def test_user_logout_invalid_token(client):
    """Test logout with invalid token."""
    response = client.post("/api/v1/auth/logout", headers={
        "Authorization": "Bearer invalidtoken"
    })
    
    # Logout always returns 204, even for invalid tokens (security by design)
    assert response.status_code == 204


def test_protected_endpoint_without_auth(client):
    """Test accessing protected endpoint without authentication."""
    response = client.post("/api/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "Hello"}]
    })
    
    assert response.status_code == 401


def test_protected_endpoint_with_valid_auth(client, test_user):
    """Test accessing protected endpoint with valid authentication."""
    # Login to get token
    login_response = client.post("/api/v1/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })
    token = login_response.json()["token"]
    
    # Try to access protected endpoint (will fail due to no upstream API, but should pass auth)
    response = client.post("/api/v1/chat/completions", 
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "Hello"}]}
    )
    
    # Should not be 401 (unauthorized), might be other error due to no upstream API
    assert response.status_code != 401


def test_token_expiration_handling():
    """Test token expiration logic."""
    username = "expiretest"
    password = "testpass"
    
    # Clean up
    try:
        storage.delete_user_by_username(username)
    except:
        pass
    
    user_id = storage.create_user(username, password)
    token = storage.issue_token(user_id)
    
    # Token should be valid initially
    user = storage.get_user_by_token(token)
    assert user is not None
    assert user["id"] == user_id
    
    # Revoke token
    storage.revoke_token(token)
    
    # Token should be invalid after revocation
    user = storage.get_user_by_token(token)
    assert user is None


def test_user_isolation():
    """Test that users can only access their own data."""
    import uuid
    # Create two users with unique names
    user1_name = f"user1_{uuid.uuid4().hex[:8]}"
    user2_name = f"user2_{uuid.uuid4().hex[:8]}"
    user1_id = storage.create_user(user1_name, "pass1")
    user2_id = storage.create_user(user2_name, "pass2")
    
    # Create conversations for each user
    conv1_id = storage.create_conversation(user1_id, "User 1 Chat")
    conv2_id = storage.create_conversation(user2_id, "User 2 Chat")
    
    # User 1 should only see their conversation
    user1_convs = storage.list_conversations(user1_id)
    assert len(user1_convs) == 1
    assert user1_convs[0]["id"] == conv1_id
    
    # User 2 should only see their conversation
    user2_convs = storage.list_conversations(user2_id)
    assert len(user2_convs) == 1
    assert user2_convs[0]["id"] == conv2_id
    
    # Clean up
    storage.delete_conversation_by_id(conv1_id)
    storage.delete_conversation_by_id(conv2_id)


def test_password_security():
    """Test password hashing and verification."""
    username = "securitytest"
    password = "mysecretpassword"
    
    # Clean up
    try:
        storage.delete_user_by_username(username)
    except:
        pass
    
    user_id = storage.create_user(username, password)
    
    # Verify password works
    user = storage.authenticate_user(username, password)
    assert user is not None
    assert user["id"] == user_id
    
    # Verify wrong password fails
    user = storage.authenticate_user(username, "wrongpassword")
    assert user is None
    
    # Check that password is not stored in plain text
    import sqlite3
    conn = sqlite3.connect(storage._DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    assert row["password_hash"] != password  # Password should be hashed
    assert len(row["password_hash"]) > 20  # Hash should be reasonably long


def test_input_validation():
    """Test input validation for auth endpoints."""
    # Test empty username
    try:
        storage.create_user("", "password")
        assert False, "Should have raised an error for empty username"
    except ValueError:
        pass
    
    # Test empty password
    try:
        storage.create_user("username", "")
        assert False, "Should have raised an error for empty password"
    except ValueError:
        pass


def test_concurrent_user_operations():
    """Test concurrent user operations."""
    import threading
    import time
    
    results = []
    errors = []
    
    def create_user_thread(i):
        try:
            username = f"concurrent_user_{i}"
            password = f"pass_{i}"
            user_id = storage.create_user(username, password)
            results.append((username, user_id))
        except Exception as e:
            errors.append(e)
    
    # Create multiple users concurrently
    threads = []
    for i in range(5):
        thread = threading.Thread(target=create_user_thread, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Should have created 5 users without errors
    assert len(errors) == 0
    assert len(results) == 5
    
    # Clean up
    for username, _ in results:
        try:
            storage.delete_user_by_username(username)
        except:
            pass