import streamlit as st
from my_chatbot.frontend import session_manager, ui_components, api_client
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다.
# 이는 streamlit run 명령이 실행될 때 .env를 자동으로 읽지 못할 경우를 대비합니다.
load_dotenv()

# 페이지 설정은 반드시 스크립트 최상단에 위치해야 합니다.
st.set_page_config(page_title="My Gemini Clone", page_icon="♊", layout="wide")

# 1. 세션 초기화
session_manager.initialize_session()

# 2. 사이드바 UI 렌더링
ui_components.render_sidebar()

# 3. 메인 화면 로직
current_chat = session_manager.get_current_chat_data()

if not current_chat:
    st.title("안녕하세요!")
    st.write("무엇을 도와드릴까요? 사이드바에서 '새 채팅'을 시작하세요.")
else:
    # 채팅 기록 렌더링
    ui_components.render_chat_history(current_chat)

    # 사용자 입력 처리
    if prompt := st.chat_input("메시지를 입력하세요..."):
        # 사용자 메시지 저장 및 즉시 표시
        current_chat["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 첫 사용자 메시지인 경우, 제목을 생성하고 UI를 새로고침하여 반영
        if len(current_chat["messages"]) == 1:
            title = prompt[:25] + "..." if len(prompt) > 25 else prompt
            current_chat["title"] = title
            st.rerun()

        # 어시스턴트 응답 처리
        with st.chat_message("assistant"):
            try:
                with st.spinner("AI가 생각 중입니다..."):
                    response_stream = api_client.stream_chat_to_backend(current_chat["messages"])
                    # 스트리밍 응답을 실시간으로 화면에 렌더링
                    full_response = st.write_stream(response_stream.iter_content())
                # 전체 응답을 대화 기록에 저장
                current_chat["messages"].append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")