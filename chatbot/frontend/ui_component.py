import streamlit as st
from . import session_manager

def render_sidebar():
    """Renders the sidebar UI components."""
    with st.sidebar:
        st.title("♊ My Gemini")
        if st.button("➕ 새 채팅", use_container_width=True, help="새로운 대화를 시작합니다."):
            session_manager.create_new_chat()

        st.markdown("---")
        st.markdown("**최근 대화**")

        # 대화 목록을 역순(최신순)으로 표시
        chat_ids = list(st.session_state.chat_history.keys())
        chat_ids.reverse()

        for chat_id in chat_ids:
            title = st.session_state.chat_history[chat_id]["title"]
            if st.button(title, key=f"chat_{chat_id}", use_container_width=True):
                st.session_state.current_chat_id = chat_id
                st.rerun()

def render_chat_history(chat_data):
    """Renders the chat messages for the given chat data."""
    for message in chat_data["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])