import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file, load_prompt_from_file

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
    existing_intake_summary = state.get('intake_summary_report', '')  # Re-Intake 모드에서 기존 Summary 보존
    
    # 3. 프롬프트 및 컨텍스트 로드 (매번 새로 로드)
    
    # Re-Intake 모드일 때는 re_intake 프롬프트 사용
    if is_re_intake:
        base_prompt = load_prompt_from_file("stage1_re_intake.md")
        if not base_prompt:
            base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        else:
            pass
    else:
        base_prompt = load_prompt_from_file("stage1_intake.md")
        if not base_prompt:
            base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        else:
            pass

    context_data = {}
    
    # (1) 필수 정보 Context (매번 새로 로드)
    intake_context = load_context_from_file("stage_specific/context_stage1_intake.json")
    if intake_context:
        try:
            context_data["mandatory_fields"] = json.loads(intake_context)
        except json.JSONDecodeError:
            context_data["mandatory_fields"] = intake_context
    else:
        pass
    
    # (2) 도메인 정보 Context (매번 새로 로드)
    domains_context = load_context_from_file("stage_specific/context_stage1_domains.json")
    if domains_context:
        try:
            context_data["domains_info"] = json.loads(domains_context)
        except json.JSONDecodeError:
            context_data["domains_info"] = domains_context
    else:
        pass
    
    # (3) Re-Intake Context (Re-Intake 모드일 때만 로드)
    if is_re_intake:
        re_intake_context = load_context_from_file("stage_specific/context_stage1_re_intake.json")
        if re_intake_context:
            try:
                context_data["re_intake_guide"] = json.loads(re_intake_context)
            except json.JSONDecodeError:
                context_data["re_intake_guide"] = re_intake_context
        else:
            pass

    # 4. System Prompt 구성 (LLM 지시사항)
    # 필수 필드 수집 상태 확인을 위한 히스토리 분석
    collected_fields_hint = ""
    if messages:
        # 최근 대화에서 수집된 필드 힌트 제공
        recent_messages = "\n".join([msg.content for msg in messages[-10:] if isinstance(msg, (HumanMessage, AIMessage))])
        collected_fields_hint = f"\n## 현재까지 수집된 정보 힌트\n(다음 대화 기록을 분석하여 이미 수집된 필수 필드를 파악하세요)\n{recent_messages[:1000]}\n"
    
    # Re-Intake 모드일 때 기존 Summary 포함
    existing_summary_section = ""
    if is_re_intake and existing_intake_summary:
        existing_summary_section = f"""

## ⚠️⚠️⚠️ 매우 중요: 기존 Intake Summary Report (절대 변경 금지!)
다음은 이전에 수집된 정보입니다. **주요_증상 필드는 절대 변경하지 마세요!** 기존 내용을 그대로 유지해야 합니다.

```
{existing_intake_summary}
```

**Re-Intake 모드 규칙:**
1. **주요_증상 필드는 절대 변경하거나 다시 질문하지 마세요!** 기존 내용을 그대로 유지해야 합니다.
2. 다른 필드(수면, 식욕_체중, 활력_에너지, 신체증상)만 보강하거나 구체화하세요.
3. 새로운 정보를 수집한 후, 기존 Summary에 추가 정보만 병합하여 보강된 Summary를 생성하세요.
4. Summary 생성 시 기존 주요_증상을 그대로 포함하고, 다른 필드는 새로운 정보로 보강하세요.
"""
    
    system_instructions = f"""
{base_prompt}
{collected_fields_hint}
{existing_summary_section}

## 현재 상담 상태 정보
- **Re-Intake 모드**: {"예 (추가 탐색 필요)" if is_re_intake else "아니오 (일반 진행)"}
- **도메인 심화 질문 모드**: {"예" if domain_active else "아니오"}
- **현재 탐색 중인 도메인**: {current_domain if current_domain else "없음"}

## 필수 필드 수집 및 처리 가이드
이 프롬프트 하단에 첨부된 **Context Data (mandatory_fields)** 를 기준으로 대화를 진행하세요.

1. **필수 필드 확인**: `mandatory_fields`에 정의된 5가지 항목(주요_증상, 수면, 식욕_체중, 활력_에너지, 신체증상)을 모두 수집해야 합니다.
2. **답변 분류**: 사용자의 답변은 반드시 Context의 `problem_types` 목록에 있는 용어로 분류하여 기록하세요. (주요_증상 제외)
3. **주요_증상 기록**: 주요_증상은 사용자의 구체적인 호소 내용을 문장 형태로 기록하세요.

## 동적 지시사항
1. **도메인 감지**: 대화 중 13개 도메인(우울, 불안 등)과 관련된 강력한 징후가 발견되면 `---INTERNAL_DATA---` 섹션에 `DOMAIN_DETECTED: [도메인명]`을 출력하세요.
2. **도메인 질문 완료**: 도메인 심화 질문이 완료되면 `DOMAIN_COMPLETED: True`를 출력하여 필수 정보 수집으로 복귀하세요.
3. **완료 조건**: 5가지 필수 정보가 모두 수집되었다고 판단될 때만 `Summary String:`을 생성하세요.

## 출력 형식 (Strict)
먼저 사용자에게 보낼 공감적인 메시지를 작성하고, 그 뒤에 시스템 데이터를 작성하세요.

[사용자 응답 메시지]

---INTERNAL_DATA---
FIELD_COLLECTION_STATUS:
- 주요_증상: [수집됨/미수집]
- 수면: [수집됨/미수집]
- 식욕_체중: [수집됨/미수집]
- 활력_에너지: [수집됨/미수집]
- 신체증상: [수집됨/미수집]

DOMAIN_DETECTED: [도메인명] (감지된 경우만)
DOMAIN_COMPLETED: [True] (완료된 경우만)

Summary String:
(모든 필수 정보가 수집된 경우에만 작성. Context의 `intake_summary_report` 예시 형식을 따를 것)
"""

    # Context 문자열 변환
    context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
    
    # 5. LLM 호출
    # ask_gemini에 system_instructions와 context_str을 합쳐서 전달
    # f-string 대신 문자열 연결 사용하여 JSON 중괄호 문제 방지
    full_context = system_instructions + "\n\n## 참고할 Context Data\n" + context_str
    
    # 히스토리에서 마지막 사용자 메시지 제거 및 길이 제한
    # ask_gemini는 user_input을 prompt에 포함시키므로 history에는 이전 대화만 남김
    previous_history = history[:-1] if history else []
    
    # Intake 단계는 초기 단계이므로 최근 대화만 전달 (너무 많은 히스토리 방지)
    # 최대 10개 메시지 (5쌍)로 제한
    if len(previous_history) > 10:
        previous_history = previous_history[-10:]
    
    # 디버깅: 프롬프트 구성 확인
    
    response_text = ask_openai(
        user_input=user_input,
        context=full_context,
        conversation_history=previous_history
    )
    
    # 6. 응답 파싱 및 State 업데이트
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
        if state.get("is_re_intake"):
            if "?" in response_text:
                state["re_intake_questions_asked"] = state.get("re_intake_questions_asked", 0) + 1

    # 필수 필드 수집 상태 추적
    field_status = {
        "주요_증상": "미수집",
        "수면": "미수집",
        "식욕_체중": "미수집",
        "활력_에너지": "미수집",
        "신체증상": "미수집"
    }
    
    # FIELD_COLLECTION_STATUS 파싱
    if "FIELD_COLLECTION_STATUS:" in internal_data:
        status_section = internal_data.split("FIELD_COLLECTION_STATUS:")[1]
        if "Summary String:" in status_section:
            status_section = status_section.split("Summary String:")[0]
        for line in status_section.split('\n'):
            line = line.strip()
            if not line or line.startswith('-') and ':' in line:
                # "- 필드명: 상태" 형식 파싱
                for field_name in field_status.keys():
                    if field_name in line:
                        if "수집됨" in line or "충분" in line:
                            field_status[field_name] = "수집됨"
                        elif "부족" in line or "부분" in line:
                            field_status[field_name] = "부족"
                        elif "미수집" in line or "없음" in line:
                            field_status[field_name] = "미수집"
    
    # 모든 필드가 수집되었는지 확인
    all_fields_collected = all(
        status == "수집됨" for status in field_status.values()
    )
    
    # (1) 도메인 감지 처리
    if "DOMAIN_DETECTED:" in internal_data:
        for line in internal_data.split('\n'):
            if "DOMAIN_DETECTED:" in line:
                detected_domain = line.replace("DOMAIN_DETECTED:", "").strip()
                if detected_domain and detected_domain.lower() != "none":
                    new_state["domain_questions_active"] = True
                    new_state["current_domain"] = detected_domain
                    break
                    
    # (2) 도메인 질문 완료 처리
    if "DOMAIN_COMPLETED: True" in internal_data:
        new_state["domain_questions_active"] = False
        new_state["current_domain"] = None
        
    # (3) Summary String (필수 정보 수집 완료) 처리 및 검증
    if "Summary String:" in internal_data:
        summary_parts = internal_data.split("Summary String:")
        if len(summary_parts) > 1:
            summary_content = summary_parts[1].strip()
            
            # 필수 필드 검증: Summary에 5가지 필수 필드가 모두 포함되어 있는지 확인
            required_fields = ["주요_증상", "수면", "식욕_체중", "활력_에너지", "신체증상"]
            missing_fields = []
            
            for field in required_fields:
                # 필드명의 주요 키워드가 Summary에 포함되어 있는지 확인
                field_keywords = {
                    "주요_증상": ["주요", "증상", "기분", "상담", "이유"],
                    "수면": ["수면", "잠", "불면", "수면장애"],
                    "식욕_체중": ["식욕", "체중", "음식", "먹"],
                    "활력_에너지": ["활력", "에너지", "피로", "기력", "집중"],
                    "신체증상": ["신체", "두통", "가슴", "심장", "호흡", "근육"]
                }
                
                field_found = any(
                    keyword in summary_content 
                    for keyword in field_keywords.get(field, [])
                )
                
                if not field_found:
                    missing_fields.append(field)
            
            # 모든 필드가 수집되었고 Summary에도 포함되어 있으면 수락
            if all_fields_collected and len(missing_fields) == 0:
                # Re-Intake 모드일 때: 기존 주요_증상 보존
                if is_re_intake and existing_intake_summary:
                    # 기존 Summary에서 주요_증상 추출
                    existing_chief_complaint = ""
                    if "주요_증상:" in existing_intake_summary or "주요증상:" in existing_intake_summary:
                        # 기존 Summary에서 주요_증상 부분 추출
                        for line in existing_intake_summary.split('\n'):
                            if "주요_증상:" in line or "주요증상:" in line:
                                # "주요_증상:" 또는 "주요증상:" 뒤의 내용 추출
                                parts = line.split(":", 1)
                                if len(parts) > 1:
                                    existing_chief_complaint = parts[1].strip()
                                    break
                    
                    # 새 Summary에서 주요_증상 부분을 기존 것으로 교체
                    if existing_chief_complaint:
                        # 새 Summary에서 주요_증상 라인 찾아서 교체
                        new_summary_lines = summary_content.split('\n')
                        for i, line in enumerate(new_summary_lines):
                            if "주요_증상:" in line or "주요증상:" in line:
                                # 기존 주요_증상으로 교체
                                if "주요_증상:" in line:
                                    new_summary_lines[i] = f"주요_증상: {existing_chief_complaint}"
                                else:
                                    new_summary_lines[i] = f"주요증상: {existing_chief_complaint}"
                                break
                        summary_content = '\n'.join(new_summary_lines)
                
                new_state["intake_summary_report"] = summary_content
            else:
                # 검증 실패: Summary 생성하지 않음
                if missing_fields:
                    pass
                # Summary를 생성하지 않았으므로 계속 정보 수집 단계 유지
                if "Summary String:" in user_message:
                    # 사용자에게 보낼 메시지에서 Summary 부분 제거
                    user_message = user_message.split("---INTERNAL_DATA---")[0].strip()
                    if "Summary String:" in user_message:
                        user_message = user_message.split("Summary String:")[0].strip()
    
    # 7. 결과 반환
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }
