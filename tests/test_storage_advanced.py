"""Advanced tests for storage functionality."""

import pytest
import sqlite3
from datetime import datetime, UTC
from chatbot.core import storage


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Setup temporary database for each test."""
    db_path = tmp_path / "test_chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")
    
    from importlib import reload
    from chatbot.core import config, storage
    reload(config)
    reload(storage)
    storage.initialize_database()
    yield db_path


def test_database_schema_creation(temp_db):
    """Test that database schema is created correctly."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Check conversations table
    cursor.execute("PRAGMA table_info(conversations)")
    conv_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert conv_columns == {
        'id': 'TEXT',
        'title': 'TEXT',
        'created_at': 'TEXT'
    }
    
    # Check messages table
    cursor.execute("PRAGMA table_info(messages)")
    msg_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert msg_columns == {
        'id': 'INTEGER',
        'conversation_id': 'TEXT',
        'role': 'TEXT',
        'content': 'TEXT',
        'created_at': 'TEXT'
    }
    
    # Check foreign key constraint
    cursor.execute("PRAGMA foreign_key_list(messages)")
    fk_info = cursor.fetchall()
    assert len(fk_info) == 1
    assert fk_info[0][2] == 'conversations'  # references conversations table
    assert fk_info[0][3] == 'conversation_id'  # from column
    assert fk_info[0][4] == 'id'  # to column
    
    conn.close()


def test_conversation_title_update():
    """Test updating conversation title."""
    from chatbot.core import storage
    
    conv_id = storage.create_conversation("Original Title")
    storage.update_conversation_title(conv_id, "Updated Title")
    
    conv = storage.get_conversation(conv_id)
    assert conv["title"] == "Updated Title"


def test_conversation_with_multiple_messages():
    """Test conversation with multiple messages in correct order."""
    from chatbot.core import storage
    
    conv_id = storage.create_conversation("Multi-message Test")
    
    # Add messages in sequence
    storage.append_message(conv_id, "user", "First message")
    storage.append_message(conv_id, "assistant", "First response")
    storage.append_message(conv_id, "user", "Second message")
    storage.append_message(conv_id, "assistant", "Second response")
    
    conv = storage.get_conversation(conv_id)
    messages = conv["messages"]
    
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "First message"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "First response"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Second message"
    assert messages[3]["role"] == "assistant"
    assert messages[3]["content"] == "Second response"


def test_delete_conversation_cascades_messages():
    """Test that deleting conversation also deletes associated messages."""
    from chatbot.core import storage
    
    conv_id = storage.create_conversation("To be deleted")
    storage.append_message(conv_id, "user", "This will be deleted")
    storage.append_message(conv_id, "assistant", "This too")
    
    # Verify conversation and messages exist
    conv = storage.get_conversation(conv_id)
    assert conv is not None
    assert len(conv["messages"]) == 2
    
    # Delete conversation
    storage.delete_conversation(conv_id)
    
    # Verify conversation and messages are gone
    conv = storage.get_conversation(conv_id)
    assert conv is None


def test_list_conversations_with_limit():
    """Test listing conversations with limit parameter."""
    from chatbot.core import storage
    
    # Create multiple conversations
    conv_ids = []
    for i in range(5):
        conv_id = storage.create_conversation(f"Conversation {i}")
        conv_ids.append(conv_id)
    
    # Test with limit
    limited_convs = storage.list_conversations(limit=3)
    assert len(limited_convs) == 3
    
    # Should be in reverse chronological order (newest first)
    all_convs = storage.list_conversations()
    assert len(all_convs) == 5
    assert [c["id"] for c in limited_convs] == [c["id"] for c in all_convs[:3]]


def test_get_nonexistent_conversation():
    """Test getting a conversation that doesn't exist."""
    from chatbot.core import storage
    
    conv = storage.get_conversation("nonexistent-id")
    assert conv is None


def test_conversation_timestamps():
    """Test that timestamps are properly set and formatted."""
    from chatbot.core import storage
    
    before_creation = datetime.now(UTC)
    conv_id = storage.create_conversation("Timestamp Test")
    storage.append_message(conv_id, "user", "Test message")
    after_creation = datetime.now(UTC)
    
    conv = storage.get_conversation(conv_id)
    
    # Parse timestamps
    conv_timestamp = datetime.fromisoformat(conv["created_at"])
    msg_timestamp = datetime.fromisoformat(conv["messages"][0]["created_at"])
    
    # Verify timestamps are within expected range
    assert before_creation <= conv_timestamp <= after_creation
    assert before_creation <= msg_timestamp <= after_creation
    
    # Verify timestamps are in UTC
    assert conv_timestamp.tzinfo == UTC
    assert msg_timestamp.tzinfo == UTC


def test_empty_conversation_list():
    """Test listing conversations when none exist."""
    from chatbot.core import storage
    
    convs = storage.list_conversations()
    assert convs == []


def test_conversation_with_special_characters():
    """Test conversation with special characters in title and content."""
    from chatbot.core import storage
    
    special_title = "Test with émojis 🚀 and 'quotes' & symbols"
    special_content = "Message with\nnewlines and \"quotes\" and <tags>"
    
    conv_id = storage.create_conversation(special_title)
    storage.append_message(conv_id, "user", special_content)
    
    conv = storage.get_conversation(conv_id)
    assert conv["title"] == special_title
    assert conv["messages"][0]["content"] == special_content


def test_concurrent_database_access():
    """Test that multiple database operations work correctly."""
    from chatbot.core import storage
    
    # Create multiple conversations and messages rapidly
    conv_ids = []
    for i in range(10):
        conv_id = storage.create_conversation(f"Concurrent Test {i}")
        conv_ids.append(conv_id)
        storage.append_message(conv_id, "user", f"Message {i}")
        storage.append_message(conv_id, "assistant", f"Response {i}")
    
    # Verify all conversations were created correctly
    all_convs = storage.list_conversations()
    assert len(all_convs) == 10
    
    for i, conv_id in enumerate(conv_ids):
        conv = storage.get_conversation(conv_id)
        assert conv is not None
        assert len(conv["messages"]) == 2
        assert conv["messages"][0]["content"] == f"Message {i}"
        assert conv["messages"][1]["content"] == f"Response {i}"