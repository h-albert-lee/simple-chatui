"""Session management helpers for the Streamlit frontend."""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

from chatbot.core import storage
from chatbot.core.config import settings


def initialize_session() -> None:
    """Initialise Streamlit session state and SQLite storage."""

    storage.initialize_database()

    if "conversations" not in st.session_state:
        conversations = {}
        for convo in storage.list_conversations():
            details = storage.get_conversation(convo["id"])
            conversations[convo["id"]] = {
                "id": convo["id"],
                "title": convo["title"],
                "messages": [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in details["messages"]
                ]
                if details
                else [],
            }
        st.session_state.conversations = conversations

    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = next(iter(st.session_state.conversations), None)

    if "selected_model" not in st.session_state:
        st.session_state.selected_model = settings.DEFAULT_MODEL


def list_conversations() -> List[Dict[str, str]]:
    ordered = []
    for convo in storage.list_conversations():
        data = st.session_state.conversations.get(convo["id"])
        if not data:
            _load_conversation_into_state(convo["id"], set_current=False)
            data = st.session_state.conversations.get(
                convo["id"],
                {"id": convo["id"], "title": convo["title"], "messages": []},
            )
        ordered.append({"id": convo["id"], "title": data["title"]})
    return ordered


def get_current_chat() -> Optional[Dict[str, object]]:
    chat_id = st.session_state.get("current_chat_id")
    if not chat_id:
        return None
    return st.session_state.conversations.get(chat_id)


def _load_conversation_into_state(chat_id: str, set_current: bool = True) -> None:
    conversation = storage.get_conversation(chat_id)
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
    _load_conversation_into_state(chat_id, set_current=True)


def get_selected_model() -> str:
    return st.session_state.get("selected_model", settings.DEFAULT_MODEL)


def set_selected_model(model_name: str) -> None:
    st.session_state.selected_model = model_name


def create_new_chat() -> None:
    chat_id = storage.create_conversation()
    st.session_state.conversations[chat_id] = {
        "id": chat_id,
        "title": "새로운 대화",
        "messages": [],
    }
    st.session_state.current_chat_id = chat_id


def append_message(role: str, content: str) -> None:
    chat_id = st.session_state.current_chat_id
    if not chat_id:
        return

    storage.append_message(chat_id, role, content)
    st.session_state.conversations[chat_id]["messages"].append(
        {"role": role, "content": content}
    )


def update_title_if_needed(prompt: str) -> None:
    chat_id = st.session_state.current_chat_id
    if not chat_id:
        return

    conversation = st.session_state.conversations[chat_id]
    if conversation["title"] != "새로운 대화":
        return

    title = prompt.strip().splitlines()[0][:40]
    if not title:
        title = "대화"
    storage.update_conversation_title(chat_id, title)
    conversation["title"] = title


def delete_conversation(chat_id: str) -> None:
    if chat_id in st.session_state.conversations:
        storage.delete_conversation(chat_id)
        st.session_state.conversations.pop(chat_id, None)
        if st.session_state.current_chat_id == chat_id:
            st.session_state.current_chat_id = next(
                iter(st.session_state.conversations), None
            )
