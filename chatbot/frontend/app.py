"""Streamlit application entry point."""

from __future__ import annotations

from typing import List

import streamlit as st
from dotenv import load_dotenv

from chatbot.frontend import api_client, session_manager, ui_component

load_dotenv()

st.set_page_config(page_title="Simple ChatUI", page_icon="💬", layout="wide")

session_manager.initialize_session()
ui_component.render_sidebar()

current_chat = session_manager.get_current_chat()

if not current_chat or not current_chat.get("messages"):
    st.title("간단한 ChatGPT 스타일 인터페이스")
    st.write(
        "좌측 사이드바에서 새 대화를 시작하고, 모델을 선택한 뒤 메시지를 입력해보세요."
    )
else:
    ui_component.render_chat_history(current_chat)

prompt = st.chat_input("메시지를 입력하세요…")

if prompt:
    if not current_chat:
        session_manager.create_new_chat()
        current_chat = session_manager.get_current_chat()

    session_manager.append_message("user", prompt)
    current_chat = session_manager.get_current_chat()

    with st.chat_message("user"):
        st.markdown(prompt)

    session_manager.update_title_if_needed(prompt)

    model_name = session_manager.get_selected_model()

    with st.chat_message("assistant"):
        collected_chunks: List[str] = []
        response_container = st.empty()
        try:
            for chunk in api_client.stream_chat_completion(
                current_chat["messages"], model=model_name
            ):
                collected_chunks.append(chunk)
                response_container.markdown("".join(collected_chunks))
        except Exception as exc:  # broad to display feedback in UI
            st.error(f"응답을 가져오는 중 오류가 발생했습니다: {exc}")
        else:
            full_response = "".join(collected_chunks)
            if full_response:
                session_manager.append_message("assistant", full_response)

    st.experimental_rerun()
