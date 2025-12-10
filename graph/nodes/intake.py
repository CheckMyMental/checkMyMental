import json
import os
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file

def intake_node(state: CounselingState) -> Dict[str, Any]:
    """
    Intake Stage (1단계) 처리 노드
    - 필수 정보 수집
    - 도메인 심화 질문
    - Re-Intake 처리
    """
    
    # 1. 메시지 히스토리 준비
    messages = state['messages']
    if not messages:
        # 초기 진입 시 (메시지가 없을 경우)
        user_input = "상담을 시작합니다." #내부 트리거, 사용자가 입력하는건 아님.
    else:
        last_message = messages[-1] #마지막 사용자 메세지 추출
        if isinstance(last_message, HumanMessage):
            user_input = last_message.content
        else:
            # 시스템이나 AI 메시지가 마지막인 경우 (드물지만 방어 코드)
            user_input = "계속 진행해주세요."
            
    # Gemini API용 히스토리 변환
    history = []
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        history.append({"role": role, "content": msg.content})
    
    # 2. 현재 상태 확인
    domain_active = state.get('domain_questions_active', False)
    current_domain = state.get('current_domain', None)
    is_re_intake = state.get('is_re_intake', False)
    
    # 3. 프롬프트 및 컨텍스트 로드
    # 프롬프트 파일 경로 (프로젝트 루트 기준)
    prompt_path = Path("prompts/stage1_intake.md")
    sources = []
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        sources.append(str(prompt_path))
    except Exception as e:
        base_prompt = f"기본 프롬프트 로드 중 오류 발생: {e}"

    context_data = {}
    
    # (1) 필수 정보 Context
    intake_context_file = "stage_specific/context_stage1_intake.json"
    intake_context = load_context_from_file(intake_context_file)
    if intake_context:
        try:
            context_data["mandatory_fields"] = json.loads(intake_context)
        except json.JSONDecodeError:
            context_data["mandatory_fields"] = intake_context
        sources.append(intake_context_file)
    
    # (2) 도메인 정보 Context
    domains_context_file = "stage_specific/context_stage1_domains.json"
    domains_context = load_context_from_file(domains_context_file)
    if domains_context:
        try:
            context_data["domains_info"] = json.loads(domains_context)
        except json.JSONDecodeError:
            context_data["domains_info"] = domains_context
        sources.append(domains_context_file)
    
    # (3) Re-Intake Context
    if is_re_intake:
        re_intake_context_file = "stage_specific/context_stage1_re_intake.json"
        re_intake_context = load_context_from_file(re_intake_context_file)
        if re_intake_context:
            try:
                context_data["re_intake_guide"] = json.loads(re_intake_context)
            except json.JSONDecodeError:
                context_data["re_intake_guide"] = re_intake_context
            sources.append(re_intake_context_file)

    # 4. System Prompt 구성 (LLM 지시사항)
    system_instructions = f"""
{base_prompt}

## 현재 상담 상태 정보
- **Re-Intake 모드**: {"예 (추가 탐색 필요)" if is_re_intake else "아니오 (일반 진행)"}
- **도메인 심화 질문 모드**: {"예" if domain_active else "아니오"}
- **현재 탐색 중인 도메인**: {current_domain if current_domain else "없음"}

## 동적 지시사항
1. **도메인 감지**: 사용자의 발언에서 '13개 도메인' 중 하나와 관련된 강력한 징후가 발견되면, `---INTERNAL_DATA---` 섹션에 `DOMAIN_DETECTED: [도메인명]`을 출력하세요.
2. **도메인 질문 완료**: 도메인 심화 질문이 충분히 이루어졌다고 판단되면, `DOMAIN_COMPLETED: True`를 출력하여 일반 필수 정보 수집으로 복귀하세요.
3. **필수 정보 수집 완료**: 5가지 필수 정보가 모두 충분히 수집되었다면, `Summary String:` 태그 뒤에 요약 리포트를 작성하세요.

## 출력 형식 (엄격 준수)
먼저 사용자에게 보낼 공감적이고 자연스러운 응답을 작성하세요. 그 후, 시스템 처리를 위한 데이터는 반드시 `---INTERNAL_DATA---` 구분선 아래에 작성하세요.

[사용자에게 보낼 응답 메시지]

---INTERNAL_DATA---
DOMAIN_DETECTED: [도메인명] (선택사항)
DOMAIN_COMPLETED: [True] (선택사항)
Summary String:
[요약 리포트 내용]
"""

    # Context 문자열 변환
    context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
    
    # 5. LLM 호출
    # ask_openai에 system_instructions와 context_str을 합쳐서 전달
    full_context = f"{system_instructions}\n\n## 참고할 Context Data\n{context_str}"
    
    # 히스토리에서 마지막 사용자 메시지 제거 (ask_openai 내부 로직과의 중복 방지 및 명확성 위해)
    # ask_openai는 user_input을 prompt에 포함시키므로 history에는 이전 대화만 남기는 게 좋음
    previous_history = history[:-1] if history else []
    
    response_text = ask_openai(
        user_input=user_input,
        context=full_context,
        conversation_history=previous_history,
        stage_name="intake",
        context_sources=sources,
    )
    
    # 6. 응답 파싱 및 State 업데이트
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
    
    # (1) 도메인 감지 처리
    if "DOMAIN_DETECTED:" in internal_data:
        for line in internal_data.split('\n'):
            if "DOMAIN_DETECTED:" in line:
                detected_domain = line.replace("DOMAIN_DETECTED:", "").strip()
                if detected_domain and detected_domain.lower() != "none":
                    new_state["domain_questions_active"] = True
                    new_state["current_domain"] = detected_domain
                    # 도메인 감지됨 로그 (선택사항)
                    # print(f"도메인 감지됨: {detected_domain}")
                    break
                    
    # (2) 도메인 질문 완료 처리
    if "DOMAIN_COMPLETED: True" in internal_data:
        new_state["domain_questions_active"] = False
        new_state["current_domain"] = None
        
    # (3) Summary String (필수 정보 수집 완료) 처리
    if "Summary String:" in internal_data:
        summary_parts = internal_data.split("Summary String:")
        if len(summary_parts) > 1:
            summary_content = summary_parts[1].strip()
            new_state["intake_summary_report"] = summary_content
    
    # 7. 결과 반환
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }

