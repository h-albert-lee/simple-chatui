import sqlite3
from datetime import UTC, datetime
from threading import Thread
from time import sleep

import pytest


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")

    from importlib import reload
    from chatbot.core import config, storage

    reload(config)
    reload(storage)
    storage.initialize_database()
    yield db_path


def _create_user(username="tester", password="secret"):
    from chatbot.core import storage

    return storage.create_user(username, password)


def _make_conversation(user_id, title):
    from chatbot.core import storage

    conv_id = storage.create_conversation(user_id, title)
    return conv_id


def test_database_schema_creation(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert {
        "id": "TEXT",
        "username": "TEXT",
        "password_hash": "TEXT",
        "password_salt": "TEXT",
        "created_at": "TEXT",
    }.items() <= user_columns.items()

    cursor.execute("PRAGMA table_info(sessions)")
    session_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert session_columns["token_hash"] == "TEXT"
    assert session_columns["user_id"] == "TEXT"

    cursor.execute("PRAGMA table_info(conversations)")
    conv_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert conv_columns["user_id"] == "TEXT"
    assert conv_columns["title"] == "TEXT"

    cursor.execute("PRAGMA table_info(messages)")
    msg_columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert msg_columns["conversation_id"] == "TEXT"
    assert msg_columns["role"] == "TEXT"

    conn.close()


def test_conversation_title_update():
    from chatbot.core import storage

    user_id = _create_user()
    conv_id = storage.create_conversation(user_id, "Original Title")
    storage.update_conversation_title(user_id, conv_id, "Updated Title")

    conv = storage.get_conversation(user_id, conv_id)
    assert conv["title"] == "Updated Title"


def test_conversation_with_multiple_messages():
    from chatbot.core import storage

    user_id = _create_user()
    conv_id = storage.create_conversation(user_id, "Multi-message Test")

    storage.append_message(user_id, conv_id, "user", "First message")
    storage.append_message(user_id, conv_id, "assistant", "First response")
    storage.append_message(user_id, conv_id, "user", "Second message")
    storage.append_message(user_id, conv_id, "assistant", "Second response")

    conv = storage.get_conversation(user_id, conv_id)
    messages = conv["messages"]
    assert len(messages) == 4
    assert messages[0]["content"] == "First message"
    assert messages[-1]["content"] == "Second response"


def test_delete_conversation_cascades_messages():
    from chatbot.core import storage

    user_id = _create_user()
    conv_id = storage.create_conversation(user_id, "To be deleted")
    storage.append_message(user_id, conv_id, "user", "This will be deleted")

    assert storage.get_conversation(user_id, conv_id) is not None
    storage.delete_conversation(user_id, conv_id)
    assert storage.get_conversation(user_id, conv_id) is None


def test_list_conversations_with_limit():
    from chatbot.core import storage

    user_id = _create_user()
    ids = [storage.create_conversation(user_id, f"Conversation {i}") for i in range(5)]

    limited = storage.list_conversations(user_id, limit=3)
    assert len(limited) == 3
    all_convs = storage.list_conversations(user_id)
    assert [c["id"] for c in limited] == [c["id"] for c in all_convs[:3]]
    assert all(c["id"] in ids for c in all_convs)


def test_conversation_isolated_between_users():
    from chatbot.core import storage

    user_a = _create_user("alice", "pass1")
    user_b = _create_user("bob", "pass2")

    conv_a = storage.create_conversation(user_a, "Alice convo")
    storage.append_message(user_a, conv_a, "user", "hi")

    assert storage.get_conversation(user_b, conv_a) is None
    assert storage.list_conversations(user_b) == []


def test_conversation_timestamps():
    from chatbot.core import storage

    user_id = _create_user()
    before_creation = datetime.now(UTC)
    conv_id = storage.create_conversation(user_id, "Timestamp Test")
    storage.append_message(user_id, conv_id, "user", "Test message")
    after_creation = datetime.now(UTC)

    conv = storage.get_conversation(user_id, conv_id)
    conv_timestamp = datetime.fromisoformat(conv["created_at"])
    msg_timestamp = datetime.fromisoformat(conv["messages"][0]["created_at"])

    assert before_creation <= conv_timestamp <= after_creation
    assert before_creation <= msg_timestamp <= after_creation
    assert conv_timestamp.tzinfo == UTC
    assert msg_timestamp.tzinfo == UTC


def test_empty_conversation_list():
    from chatbot.core import storage

    user_id = _create_user()
    assert storage.list_conversations(user_id) == []


def test_conversation_with_special_characters():
    from chatbot.core import storage

    user_id = _create_user()
    special_title = "Test with émojis 🚀 and 'quotes' & symbols"
    special_content = "Message with\nnewlines and \"quotes\" and <tags>"

    conv_id = storage.create_conversation(user_id, special_title)
    storage.append_message(user_id, conv_id, "user", special_content)

    conv = storage.get_conversation(user_id, conv_id)
    assert conv["title"] == special_title
    assert conv["messages"][0]["content"] == special_content


def test_concurrent_database_access():
    from chatbot.core import storage

    user_id = _create_user()
    conv_ids = []

    def worker(index: int):
        conv_id = storage.create_conversation(user_id, f"Concurrent Test {index}")
        storage.append_message(user_id, conv_id, "user", f"message {index}")
        conv_ids.append(conv_id)

    threads = [Thread(target=worker, args=(i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sleep(0.1)
    conversations = storage.list_conversations(user_id)
    assert len(conversations) == 5
    assert all(conv["id"] in conv_ids for conv in conversations)
