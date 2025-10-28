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
    yield


def _create_user():
    from chatbot.core import storage

    user_id = storage.create_user("tester", "secret")
    return user_id


def test_create_and_retrieve_conversation():
    from chatbot.core import storage

    user_id = _create_user()
    convo_id = storage.create_conversation(user_id, "테스트 대화")
    storage.append_message(user_id, convo_id, "user", "안녕?")
    storage.append_message(user_id, convo_id, "assistant", "안녕하세요!")

    convo = storage.get_conversation(user_id, convo_id)
    assert convo is not None
    assert convo["title"] == "테스트 대화"
    assert [msg["role"] for msg in convo["messages"]] == ["user", "assistant"]
    assert [msg["content"] for msg in convo["messages"]] == ["안녕?", "안녕하세요!"]


def test_list_conversations_returns_sorted():
    from chatbot.core import storage

    user_id = _create_user()
    first_id = storage.create_conversation(user_id, "첫 번째")
    second_id = storage.create_conversation(user_id, "두 번째")

    convos = storage.list_conversations(user_id)
    assert [c["id"] for c in convos] == [second_id, first_id]


def test_user_authentication_and_tokens():
    from chatbot.core import storage

    user_id = storage.create_user("tester2", "password")

    user = storage.authenticate_user("tester2", "password")
    assert user is not None
    assert user["id"] == user_id

    bad_user = storage.authenticate_user("tester2", "wrong")
    assert bad_user is None

    token = storage.issue_token(user_id)
    retrieved = storage.get_user_by_token(token)
    assert retrieved is not None
    assert retrieved["id"] == user_id

    storage.revoke_token(token)
    assert storage.get_user_by_token(token) is None
