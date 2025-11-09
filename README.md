# checkMyMental
정신질환판단Ai agent/소프트웨어응용산학협력프로젝트

# 프로젝트 클론 및 환경설정 가이드

## 🧭 프로젝트 세팅 가이드라인 (팀원용)

### 🎯 목적
이 문서는 새로 프로젝트를 클론한 팀원이 **동일한 개발 환경을 세팅하고 Streamlit 앱을 실행**할 수 있도록 안내합니다.

---

### 1️⃣ 프로젝트 클론 받기

먼저 GitHub 레포지토리를 로컬에 복제합니다.

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
```

> 💡 `cd your-repo`로 프로젝트 디렉토리 안에 들어가세요.

---

### 2️⃣ 가상환경(venv) 생성

이 프로젝트는 각자 독립된 Python 환경에서 동작하도록 설계되어 있습니다.  
아래 명령어로 가상환경을 생성하세요.

#### macOS / Linux

```bash
python3 -m venv venv
```

#### Windows (PowerShell)

```bash
python -m venv venv
```

---

### 3️⃣ 가상환경 활성화

#### macOS / Linux

```bash
source venv/bin/activate
```

#### Windows (PowerShell)

```bash
venv\Scripts\activate
```

> 활성화되면 터미널 앞에 `(venv)` 표시가 보입니다.  
> 예: `(venv) user@MacBook project %`

---

### 4️⃣ 패키지 설치

필요한 라이브러리를 설치합니다.

```bash
pip install -r requirements.txt
```

> 이 명령은 `requirements.txt`에 기록된 패키지 버전 그대로 설치합니다.

---

### 5️⃣ 환경 변수 설정

Gemini API 키를 저장할 `.env` 파일을 만듭니다.

```bash
touch .env
```

그리고 아래 내용을 추가하세요.

```
GEMINI_API_KEY=your_api_key_here
```

> ⚠️ `.env` 파일은 절대 Git에 올리지 마세요.  
> (`.gitignore`에 이미 포함되어 있습니다.)

---

### 6️⃣ 앱 실행

Streamlit을 실행해 프로토타입을 테스트합니다.

```bash
streamlit run app.py
```

> 브라우저가 자동으로 열리며  
> 기본 주소는: [http://localhost:8501](http://localhost:8501/)

---

### 7️⃣ FastAPI 서버 실행

```bash
python3 -m uvicorn api.main:app
```

---

### 8️⃣ Swagger로 API 확인

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
에 접속해 API 문서를 확인하세요.

- `/rag/hypothesis` 엔드포인트만 현재 사용 가능합니다.