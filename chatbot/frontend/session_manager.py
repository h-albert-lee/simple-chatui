import streamlit as st
import uuid

def initialize_session():
    """Initializes session state variables if they don't exist."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = {}
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None

def create_new_chat():
    """Creates a new chat session and sets it as the current one."""
    chat_id = str(uuid.uuid4())
    st.session_state.current_chat_id = chat_id
    st.session_state.chat_history[chat_id] = {"title": "새로운 대화", "messages": []}
    # UI를 즉시 새로고침하여 '새로운 대화' 목록이 바로 나타나게 함
    st.rerun()

def get_current_chat_data():
    """Returns the data for the currently active chat."""
    if st.session_state.current_chat_id:
        return st.session_state.chat_history.get(st.session_state.current_chat_id)
    return None