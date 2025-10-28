"""Streamlit UI components for the chat application."""

from __future__ import annotations

import streamlit as st

from chatbot.core import storage

from . import session_manager


def render_sidebar() -> None:
    with st.sidebar:
        st.title("💬 Simple ChatUI")
        st.caption("OpenAI-compatible multi-turn chat UI")
        st.text("Made by Hanwool Albert Lee.")

        user = session_manager.get_current_user()
        if user:
            st.success(f"{user['username']}님 환영합니다!")
            if st.button("로그아웃", use_container_width=True):
                session_manager.logout()
                st.rerun()
        else:
            st.info("로그인 후 대화를 이용할 수 있습니다.")
            return

        if st.button("➕ 새 대화", use_container_width=True):
            session_manager.create_new_chat()
            st.rerun()

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
                st.rerun()
            if cols[1].button("🗑️", key=f"delete_{convo['id']}"):
                session_manager.delete_conversation(convo["id"])
                st.rerun()


def render_chat_history(chat: dict[str, object]) -> None:
    for message in chat.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_auth_forms() -> None:
    st.title("간단한 ChatUI에 오신 것을 환영합니다")
    st.write("로그인하거나 새 계정을 만들어 대화를 시작해보세요.")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("아이디", key="login_username")
            password = st.text_input("비밀번호", type="password", key="login_password")
            submitted = st.form_submit_button("로그인")
        if submitted:
            try:
                session_manager.login(username, password)
            except ValueError:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            else:
                st.success("로그인에 성공했습니다!")
                st.experimental_rerun()

    with tab_signup:
        with st.form("signup_form", clear_on_submit=True):
            username = st.text_input("아이디", key="signup_username")
            password = st.text_input("비밀번호", type="password", key="signup_password")
            submitted = st.form_submit_button("회원가입")
        if submitted:
            try:
                session_manager.signup(username, password)
            except storage.UserAlreadyExistsError:
                st.error("이미 존재하는 아이디입니다.")
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success("회원가입 완료! 자동으로 로그인되었습니다.")
                st.experimental_rerun()
