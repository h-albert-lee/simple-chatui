# Simple ChatUI

Simple ChatUI는 Streamlit 기반의 ChatGPT 스타일 대화형 UI와 FastAPI 백엔드를 제공하여, 단일 OpenAI 호환 API에 연결해 멀티턴 채팅을 사용할 수 있도록 구성된 템플릿입니다. 대화 내용은 로컬 SQLite 데이터베이스에 캐싱되어 브라우저를 새로고침하거나 앱을 다시 실행해도 이전 대화가 유지됩니다.

## 주요 기능

- 💬 **ChatGPT 스타일 UI** – Streamlit의 `st.chat_message`와 사이드바를 활용한 직관적인 사용자 경험
- 🔌 **OpenAI 호환 API 프록시** – FastAPI 백엔드가 하나의 OpenAI-Compatible API에 연결되어 스트리밍 응답을 프록시
- 🔐 **멀티 사용자 인증** – 이름/비밀번호 기반 회원가입 및 로그인을 제공하고, 사용자별로 대화가 격리된 상태로 저장
- 🧠 **모델 선택 지원** – 사이드바에서 사용할 모델 이름을 입력해 즉시 반영
- 💾 **SQLite 캐시** – 대화 및 메시지를 로컬 데이터베이스에 저장하여 지속성 보장
- ✅ **프로덕션 준비** – 환경 변수 기반 설정, FastAPI + Streamlit 분리, 테스트 코드 및 문서 제공

## 디렉터리 구조

```
chatbot/
├── backend/      # FastAPI 백엔드
├── core/         # 설정 및 SQLite 스토리지
└── frontend/     # Streamlit 앱
```

## 사전 준비

1. Python 3.10 이상
2. OpenAI 호환 API 엔드포인트 및 API 키 (예: OpenAI, Azure OpenAI, vLLM 등)

## 설치 및 실행

### 1. 저장소 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env`를 생성하고 값을 수정합니다.

```bash
cp .env.example .env
```

필수 항목:

- `UPSTREAM_API_BASE`: OpenAI 호환 API의 베이스 URL (예: `https://api.openai.com`)
- `UPSTREAM_API_KEY`: API 키 (필요 없는 경우 빈 값 허용)

선택 항목:

- `DEFAULT_MODEL`: 기본으로 사용할 모델명 (사이드바에서 변경 가능)
- `BACKEND_API_URL`: 프론트엔드에서 호출할 백엔드 URL (다른 포트/호스트에 배포 시 변경)
- `DATABASE_URL`: SQLite 파일 경로 (기본값 `sqlite:///chat_history.db`)
- `AUTH_TOKEN_TTL_HOURS`: 세션 토큰 유효 기간(시간 단위, 기본 7일)

### 3. 백엔드 실행

```bash
python run_backend.py
```

백엔드는 기본적으로 `http://localhost:8000`에서 실행되며 `/api/v1/chat/completions` 엔드포인트로 프록시 요청을 수행합니다. 인증 관련 라우트는 `/api/v1/auth/*` 경로에 있으며 다음을 제공합니다.

- `POST /api/v1/auth/signup` – 사용자 생성 후 세션 토큰 반환
- `POST /api/v1/auth/login` – 기존 사용자 인증 후 세션 토큰 반환
- `POST /api/v1/auth/logout` – 제공된 토큰 폐기

### 4. 프론트엔드 실행

다른 터미널에서 아래 명령을 실행합니다.

```bash
streamlit run chatbot/frontend/app.py
```

브라우저에서 `http://localhost:8501`에 접속하면 ChatGPT와 유사한 UI를 사용할 수 있습니다.

처음 접속하면 로그인/회원가입 화면이 표시됩니다. 이름과 비밀번호를 입력해 계정을 생성하거나 로그인하면, 해당 계정으로 생성된 대화만 사이드바에 표시됩니다.

## 데이터베이스와 마이그레이션

애플리케이션 실행 시 `chat_history.db`가 없다면 자동으로 생성되며, 기존 단일 사용자 데이터를 사용할 경우에도 자동으로 마이그레이션하여 `_legacy_user` 계정으로 이전 대화를 연결합니다.

## 테스트 실행

```bash
pytest
```

테스트에서는 SQLite 스토리지 동작, 인증 및 백엔드 스트리밍 프록시 로직을 검증합니다.

## 배포 팁

- **환경 분리**: `.env` 파일 대신 Docker 비밀 또는 환경 변수 관리 도구를 사용하세요.
- **로깅**: `LOG_LEVEL` 환경 변수를 통해 백엔드 로그 레벨을 조절할 수 있습니다.
- **보안**: 프록시 대상 API 키는 백엔드에서만 사용되므로 프론트엔드에 노출되지 않습니다.
- **토큰 수명 관리**: 장기 세션을 허용하지 않으려면 `AUTH_TOKEN_TTL_HOURS` 값을 줄이고, 백엔드 로그를 통해 만료된 토큰 정리를 확인하세요.

## 라이선스

MIT
