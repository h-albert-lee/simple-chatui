"""Session management helpers for the Streamlit frontend."""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

from chatbot.core import storage
from chatbot.core.config import settings

_AUTH_STATE_KEY = "auth"
_DEFAULT_CHAT_TITLE = "새로운 대화"


def initialize_session() -> None:
    """Initialise Streamlit session state and SQLite storage."""

    storage.initialize_database()

    st.session_state.setdefault(_AUTH_STATE_KEY, {"user": None, "token": None})
    st.session_state.setdefault("conversations", {})
    st.session_state.setdefault("current_chat_id", None)
    st.session_state.setdefault("selected_model", settings.DEFAULT_MODEL)
    st.session_state.setdefault("_loaded_user_id", None)

    _sync_conversations_with_user()


def _sync_conversations_with_user() -> None:
    auth_state = st.session_state[_AUTH_STATE_KEY]
    user = auth_state.get("user")
    loaded_user_id = st.session_state.get("_loaded_user_id")

    if not user:
        st.session_state.conversations = {}
        st.session_state.current_chat_id = None
        st.session_state._loaded_user_id = None  # type: ignore[attr-defined]
        return

    user_id = user["id"]
    if loaded_user_id == user_id:
        return

    conversations: Dict[str, Dict[str, object]] = {}
    for convo in storage.list_conversations(user_id):
        details = storage.get_conversation(user_id, convo["id"])
        conversations[convo["id"]] = {
            "id": convo["id"],
            "title": convo["title"],
            "messages": [
                {"role": msg["role"], "content": msg["content"]}
                for msg in (details or {}).get("messages", [])
            ],
        }

    st.session_state.conversations = conversations
    st.session_state.current_chat_id = next(iter(conversations), None)
    st.session_state._loaded_user_id = user_id  # type: ignore[attr-defined]


def is_authenticated() -> bool:
    return bool(st.session_state[_AUTH_STATE_KEY].get("user"))


def get_current_user() -> Optional[Dict[str, str]]:
    user = st.session_state[_AUTH_STATE_KEY].get("user")
    return user if user else None


def get_auth_token() -> Optional[str]:
    token = st.session_state[_AUTH_STATE_KEY].get("token")
    return token if token else None


def list_conversations() -> List[Dict[str, str]]:
    if not is_authenticated():
        return []

    ordered: List[Dict[str, str]] = []
    user_id = st.session_state[_AUTH_STATE_KEY]["user"]["id"]
    for convo in storage.list_conversations(user_id):
        data = st.session_state.conversations.get(convo["id"])
        if not data:
            _load_conversation_into_state(user_id, convo["id"], set_current=False)
            data = st.session_state.conversations.get(
                convo["id"],
                {"id": convo["id"], "title": convo["title"], "messages": []},
            )
        ordered.append({"id": convo["id"], "title": data["title"]})
    return ordered


def get_current_chat() -> Optional[Dict[str, object]]:
    if not is_authenticated():
        return None

    chat_id = st.session_state.get("current_chat_id")
    if not chat_id:
        return None
    return st.session_state.conversations.get(chat_id)


def _load_conversation_into_state(user_id: str, chat_id: str, set_current: bool = True) -> None:
    conversation = storage.get_conversation(user_id, chat_id)
    if not conversation:
        return

    st.session_state.conversations[chat_id] = {
        "id": conversation["id"],
        "title": conversation["title"],
        "messages": [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation["messages"]
        ],
    }
    if set_current:
        st.session_state.current_chat_id = chat_id


def set_current_chat(chat_id: str) -> None:
    user = get_current_user()
    if not user:
        return
    _load_conversation_into_state(user["id"], chat_id, set_current=True)


def get_selected_model() -> str:
    return st.session_state.get("selected_model", settings.DEFAULT_MODEL)


def set_selected_model(model_name: str) -> None:
    st.session_state.selected_model = model_name


def create_new_chat() -> None:
    user = get_current_user()
    if not user:
        return

    chat_id = storage.create_conversation(user["id"], _DEFAULT_CHAT_TITLE)
    st.session_state.conversations[chat_id] = {
        "id": chat_id,
        "title": _DEFAULT_CHAT_TITLE,
        "messages": [],
    }
    st.session_state.current_chat_id = chat_id


def append_message(role: str, content: str) -> None:
    user = get_current_user()
    if not user:
        return

    chat_id = st.session_state.current_chat_id
    if not chat_id:
        return

    storage.append_message(user["id"], chat_id, role, content)
    st.session_state.conversations[chat_id]["messages"].append(
        {"role": role, "content": content}
    )


def update_title_if_needed(prompt: str) -> None:
    user = get_current_user()
    if not user:
        return

    chat_id = st.session_state.current_chat_id
    if not chat_id:
        return

    conversation = st.session_state.conversations[chat_id]
    if conversation["title"] != _DEFAULT_CHAT_TITLE:
        return

    title = prompt.strip().splitlines()[0][:40]
    if not title:
        title = "대화"
    storage.update_conversation_title(user["id"], chat_id, title)
    conversation["title"] = title


def delete_conversation(chat_id: str) -> None:
    user = get_current_user()
    if not user:
        return

    if chat_id in st.session_state.conversations:
        storage.delete_conversation(user["id"], chat_id)
        st.session_state.conversations.pop(chat_id, None)
        if st.session_state.current_chat_id == chat_id:
            st.session_state.current_chat_id = next(
                iter(st.session_state.conversations), None
            )


def login(username: str, password: str) -> Dict[str, str]:
    user = storage.authenticate_user(username, password)
    if not user:
        raise ValueError("Invalid username or password")

    token = storage.issue_token(user["id"])
    st.session_state[_AUTH_STATE_KEY] = {"user": user, "token": token}
    st.session_state._loaded_user_id = None  # type: ignore[attr-defined]
    _sync_conversations_with_user()
    return user


def signup(username: str, password: str) -> Dict[str, str]:
    try:
        user_id = storage.create_user(username, password)
    except storage.UserAlreadyExistsError as exc:
        raise exc

    user = {"id": user_id, "username": username}
    token = storage.issue_token(user_id)
    st.session_state[_AUTH_STATE_KEY] = {"user": user, "token": token}
    st.session_state._loaded_user_id = None  # type: ignore[attr-defined]
    _sync_conversations_with_user()
    return user


def logout() -> None:
    token = get_auth_token()
    if token:
        storage.revoke_token(token)
    st.session_state[_AUTH_STATE_KEY] = {"user": None, "token": None}
    st.session_state.conversations = {}
    st.session_state.current_chat_id = None
    st.session_state._loaded_user_id = None  # type: ignore[attr-defined]
