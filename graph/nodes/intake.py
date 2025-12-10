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
        user_input = "상담을 시작합니다."  # 내부 트리거, 사용자가 입력하는건 아님.
    else:
        last_message = messages[-1]  # 마지막 사용자 메세지 추출
        if isinstance(last_message, HumanMessage):
            user_input = last_message.content
        else:
            # 시스템이나 AI 메시지가 마지막인 경우 (드물지만 방어 코드)
            user_input = "계속 진행해주세요."

    # 1-1. 개발자용 치트키 처리 (요약 강제 주입)
    # 사용자가 "우울증패스"라고 입력하면, Intake 과정을 생략하고
    # 미리 정의된 Summary String을 바로 state에 주입하여 다음 단계로 넘어갑니다.
    if isinstance(messages[-1], HumanMessage) and messages[-1].content.strip() == "우울증패스":
        hardcoded_summary = (
            "주요_증상: 시험에 대한 불안감. "
            "수면: 자주 깨는 문제. "
            "식욕_체중: 식욕 감소로 체중 감소. "
            "활력_에너지: 에너지 부족과 피로감. "
            "신체증상: 소화 문제."
        )

        dev_msg = (
            "개발자 모드: 입력하신 치트키에 따라, 다음과 같은 고정 요약으로 "
            "가설 설정 단계로 바로 진행합니다.\n\n"
            f"{hardcoded_summary}"
        )

        return {
            "messages": [AIMessage(content=dev_msg)],
            "intake_summary_report": hardcoded_summary,
            "domain_questions_active": False,
            "current_domain": None,
            "is_re_intake": False,
        }
            
    # OpenAI API용 히스토리 변환
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
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
    except Exception as e:
        base_prompt = f"기본 프롬프트 로드 중 오류 발생: {e}"

    context_data = {}
    
    # (1) 필수 정보 Context
    context_files_used = []
    intake_context = load_context_from_file("stage_specific/context_stage1_intake.json")
    if intake_context:
        context_files_used.append("stage_specific/context_stage1_intake.json")
        try:
            context_data["mandatory_fields"] = json.loads(intake_context)
        except json.JSONDecodeError:
            context_data["mandatory_fields"] = intake_context
    
    # (2) 도메인 정보 Context
    domains_context = load_context_from_file("stage_specific/context_stage1_domains.json")
    if domains_context:
        context_files_used.append("stage_specific/context_stage1_domains.json")
        try:
            context_data["domains_info"] = json.loads(domains_context)
        except json.JSONDecodeError:
            context_data["domains_info"] = domains_context
    
    # (3) Re-Intake Context
    if is_re_intake:
        re_intake_context = load_context_from_file("stage_specific/context_stage1_re_intake.json")
        if re_intake_context:
            context_files_used.append("stage_specific/context_stage1_re_intake.json")
            try:
                context_data["re_intake_guide"] = json.loads(re_intake_context)
            except json.JSONDecodeError:
                context_data["re_intake_guide"] = re_intake_context

    # 4. System Prompt 구성 (LLM 지시사항)
    system_instructions = f"""
{base_prompt}

## 현재 상담 상태 정보 (참고용)
- **Re-Intake 모드**: {"예 (추가 탐색 필요)" if is_re_intake else "아니오 (일반 진행)"}
- **도메인 심화 질문 모드**: {"예" if domain_active else "아니오"}
- **현재 탐색 중인 도메인**: {current_domain if current_domain else "없음"}
"""

    # Context 문자열 변환
    context_str = json.dumps(context_data, ensure_ascii=False, indent=2)

    # 디버그: 사용한 프롬프트/컨텍스트 파일명만 로그 (콘솔)
    print("[Intake Debug] prompt_path:", str(prompt_path))
    print("[Intake Debug] context_files_used:", context_files_used)
    
    # 5. LLM 호출
    # ask_openai에 system_instructions와 context_str을 합쳐서 전달
    full_context = f"{system_instructions}\n\n## 참고할 Context Data\n{context_str}"
    
    # 히스토리에서 마지막 사용자 메시지 제거 (ask_openai 내부 로직과의 중복 방지 및 명확성 위해)
    # ask_openai는 user_input을 prompt에 포함시키므로 history에는 이전 대화만 남기는 게 좋음
    previous_history = history[:-1] if history else []
    
    response_text = ask_openai(
        user_input=user_input,
        context=full_context,
        conversation_history=previous_history
    )
    
    # 디버그: 사용자/LLM 응답 로그 (콘솔)
    print("[Intake Debug] user_input:", user_input)
    print("[Intake Debug] llm_response:", response_text)
    
    # 6. 응답 파싱 및 State 업데이트
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    # INTERNAL_DATA 구분선이 있으면 분리, 없으면 전체에서 파싱
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
    else:
        internal_data = response_text
    
    # Summary String (필수 정보 수집 완료) 처리
    if "Summary String:" in internal_data:
        summary_content = internal_data.split("Summary String:", 1)[1].strip()
        new_state["intake_summary_report"] = summary_content
    
    # 7. 결과 반환
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }

