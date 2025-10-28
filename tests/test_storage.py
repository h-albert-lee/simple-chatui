import pytest


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")
    # Reload module with new settings
    from importlib import reload

    from chatbot.core import config, storage

    reload(config)
    reload(storage)
    storage.initialize_database()
    yield
    # cleanup handled by tmp_path


def test_create_and_retrieve_conversation():
    from chatbot.core import storage

    convo_id = storage.create_conversation("테스트 대화")
    storage.append_message(convo_id, "user", "안녕?")
    storage.append_message(convo_id, "assistant", "안녕하세요!")

    convo = storage.get_conversation(convo_id)
    assert convo is not None
    assert convo["title"] == "테스트 대화"
    assert [msg["role"] for msg in convo["messages"]] == ["user", "assistant"]
    assert [msg["content"] for msg in convo["messages"]] == ["안녕?", "안녕하세요!"]


def test_list_conversations_returns_sorted():
    from chatbot.core import storage

    first_id = storage.create_conversation("첫 번째")
    second_id = storage.create_conversation("두 번째")

    convos = storage.list_conversations()
    assert [c["id"] for c in convos] == [second_id, first_id]
