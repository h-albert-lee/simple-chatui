"""Streamlit UI components for the chat application."""

from __future__ import annotations

import streamlit as st

from . import session_manager


def render_sidebar() -> None:
    with st.sidebar:
        st.title("💬 Simple ChatUI")
        st.caption("OpenAI-compatible multi-turn chat UI")

        if st.button("➕ 새 대화", use_container_width=True):
            session_manager.create_new_chat()
            st.experimental_rerun()

        st.markdown("---")
        model_name = st.text_input(
            "모델 이름",
            value=session_manager.get_selected_model(),
            help="백엔드가 연결된 OpenAI 호환 API에서 사용할 모델 이름을 입력하세요.",
        )
        if model_name:
            session_manager.set_selected_model(model_name.strip())

        st.markdown("---")
        st.subheader("대화 목록")

        conversations = session_manager.list_conversations()
        if not conversations:
            st.write("저장된 대화가 없습니다.")
        for convo in conversations:
            cols = st.columns([0.8, 0.2])
            if cols[0].button(convo["title"], key=f"select_{convo['id']}", use_container_width=True):
                session_manager.set_current_chat(convo["id"])
                st.experimental_rerun()
            if cols[1].button("🗑️", key=f"delete_{convo['id']}"):
                session_manager.delete_conversation(convo["id"])
                st.experimental_rerun()


def render_chat_history(chat: dict[str, object]) -> None:
    for message in chat.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
