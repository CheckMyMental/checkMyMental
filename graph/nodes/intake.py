import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.gemini_api import ask_gemini
from frontend.context_handler import load_context_from_file, load_prompt_from_file

def intake_node(state: CounselingState) -> Dict[str, Any]:
    """
    Intake Stage (1단계) 처리 노드
    - 필수 정보 수집
    - 도메인 심화 질문
    - Re-Intake 처리
    """
    print("=" * 60)
    print("[Stage 1: Intake] 노드 실행 시작")
    print("=" * 60)
    
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
    
    # 3. 프롬프트 및 컨텍스트 로드 (매번 새로 로드)
    print(f"[Intake Node] 프롬프트 및 컨텍스트 파일 로드 시작...")
    base_prompt = load_prompt_from_file("stage1_intake.md")
    if not base_prompt:
        base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        print(f"[Intake Node] ⚠ 프롬프트 파일 로드 실패: stage1_intake.md")
    else:
        print(f"[Intake Node] ✓ 프롬프트 로드 완료: stage1_intake.md ({len(base_prompt)} 문자)")

    context_data = {}
    
    # (1) 필수 정보 Context (매번 새로 로드)
    intake_context = load_context_from_file("stage_specific/context_stage1_intake.json")
    if intake_context:
        try:
            context_data["mandatory_fields"] = json.loads(intake_context)
            print(f"[Intake Node] ✓ 필수 정보 컨텍스트 로드 완료 ({len(intake_context)} 문자)")
        except json.JSONDecodeError:
            context_data["mandatory_fields"] = intake_context
    else:
        print(f"[Intake Node] ⚠ 필수 정보 컨텍스트 로드 실패")
    
    # (2) 도메인 정보 Context (매번 새로 로드)
    domains_context = load_context_from_file("stage_specific/context_stage1_domains.json")
    if domains_context:
        try:
            context_data["domains_info"] = json.loads(domains_context)
            print(f"[Intake Node] ✓ 도메인 정보 컨텍스트 로드 완료 ({len(domains_context)} 문자)")
        except json.JSONDecodeError:
            context_data["domains_info"] = domains_context
    else:
        print(f"[Intake Node] ⚠ 도메인 정보 컨텍스트 로드 실패")
    
    # (3) Re-Intake Context (Re-Intake 모드일 때만 로드)
    if is_re_intake:
        re_intake_context = load_context_from_file("stage_specific/context_stage1_re_intake.json")
        if re_intake_context:
            try:
                context_data["re_intake_guide"] = json.loads(re_intake_context)
                print(f"[Intake Node] ✓ Re-Intake 컨텍스트 로드 완료 ({len(re_intake_context)} 문자)")
            except json.JSONDecodeError:
                context_data["re_intake_guide"] = re_intake_context
        else:
            print(f"[Intake Node] ⚠ Re-Intake 컨텍스트 로드 실패")

    # 4. System Prompt 구성 (LLM 지시사항)
    # 필수 필드 수집 상태 확인을 위한 히스토리 분석
    collected_fields_hint = ""
    if messages:
        # 최근 대화에서 수집된 필드 힌트 제공
        recent_messages = "\n".join([msg.content for msg in messages[-10:] if isinstance(msg, (HumanMessage, AIMessage))])
        collected_fields_hint = f"\n## 현재까지 수집된 정보 힌트\n(다음 대화 기록을 분석하여 이미 수집된 필수 필드를 파악하세요)\n{recent_messages[:1000]}\n"
    
    system_instructions = f"""
{base_prompt}
{collected_fields_hint}

## 현재 상담 상태 정보
- **Re-Intake 모드**: {"예 (추가 탐색 필요)" if is_re_intake else "아니오 (일반 진행)"}
- **도메인 심화 질문 모드**: {"예" if domain_active else "아니오"}
- **현재 탐색 중인 도메인**: {current_domain if current_domain else "없음"}

## 필수 필드 수집 상태 확인 (매우 중요!)
**반드시 다음 5가지 필수 필드가 모두 충분히 수집되었는지 확인하세요:**
1. **주요_증상** (Chief Complaint): 사용자가 상담을 요청한 이유와 현재 기분
2. **수면** (Sleep): 수면 문제 유형 (불면증, 과다수면, 입면곤란, 수면유지곤란, 이른아침각성, 또는 문제없음)
3. **식욕_체중** (Appetite & Weight): 식욕/체중 변화 (식욕감소/증가, 체중감소/증가, 또는 문제없음)
4. **활력_에너지** (Energy & Vitality): 에너지 수준 (피로, 활력상실, 정신운동지연/초조, 집중력감소, 우유부단, 또는 문제없음)
5. **신체증상** (Somatic Symptoms): 신체적 불편함 (두통, 위장증상, 근육긴장, 심계항진, 호흡곤란, 흉부불편감, 현기증, 이인증, 비현실감, 또는 문제없음)

**중요 규칙:**
- 위 5가지 필드 중 하나라도 충분히 수집되지 않았다면, `Summary String:`을 생성하지 마세요!
- 모든 필드가 수집되었다고 확신할 수 있을 때만 `Summary String:`을 생성하세요!
- 필드 수집이 부족하면 계속 해당 필드에 대한 질문을 하세요!

## 동적 지시사항
1. **도메인 감지**: 사용자의 발언에서 '13개 도메인' 중 하나와 관련된 강력한 징후가 발견되면, `---INTERNAL_DATA---` 섹션에 `DOMAIN_DETECTED: [도메인명]`을 출력하세요.
2. **도메인 질문 완료**: 도메인 심화 질문이 충분히 이루어졌다고 판단되면, `DOMAIN_COMPLETED: True`를 출력하여 일반 필수 정보 수집으로 복귀하세요.
3. **필수 정보 수집 완료 검증**: 
   - 먼저 위 5가지 필수 필드가 모두 수집되었는지 확인하세요
   - 각 필드에 대한 구체적인 정보가 있는지 확인하세요
   - 모든 필드가 충분히 수집되었다고 확신할 때만 `Summary String:`을 생성하세요
   - `Summary String:`에는 반드시 5가지 필수 필드에 대한 정보를 모두 포함해야 합니다

## 출력 형식 (엄격 준수)
먼저 사용자에게 보낼 공감적이고 자연스러운 응답을 작성하세요. 그 후, 시스템 처리를 위한 데이터는 반드시 `---INTERNAL_DATA---` 구분선 아래에 작성하세요.

[사용자에게 보낼 응답 메시지]

---INTERNAL_DATA---
FIELD_COLLECTION_STATUS: [각 필드별 수집 상태를 명시적으로 표시]
- 주요_증상: [수집됨/부족/미수집]
- 수면: [수집됨/부족/미수집]
- 식욕_체중: [수집됨/부족/미수집]
- 활력_에너지: [수집됨/부족/미수집]
- 신체증상: [수집됨/부족/미수집]
DOMAIN_DETECTED: [도메인명] (선택사항)
DOMAIN_COMPLETED: [True] (선택사항)
Summary String:
[모든 5가지 필수 필드가 충분히 수집되었을 때만 작성하세요. 각 필드에 대한 구체적인 내용을 포함하세요.]
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
        print(f"[Intake Node] 히스토리 길이 제한: {len(previous_history)}개 메시지만 사용")
    
    # 디버깅: 프롬프트 구성 확인
    print(f"[Intake Node] LLM 호출 준비:")
    print(f"  - System Instructions 길이: {len(system_instructions)} 문자")
    print(f"  - Context Data 길이: {len(context_str)} 문자")
    print(f"  - Full Context 길이: {len(full_context)} 문자")
    print(f"  - 사용자 입력: {user_input[:100]}...")
    print(f"  - 히스토리 메시지 수: {len(previous_history)}개 (전체: {len(history)}개)")
    
    response_text = ask_gemini(
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
                    print(f"[Intake Node] 도메인 감지됨: {detected_domain}")
                    break
                    
    # (2) 도메인 질문 완료 처리
    if "DOMAIN_COMPLETED: True" in internal_data:
        new_state["domain_questions_active"] = False
        new_state["current_domain"] = None
        print(f"[Intake Node] 도메인 질문 완료, 일반 정보 수집 모드로 복귀")
        
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
                new_state["intake_summary_report"] = summary_content
                print(f"[Intake Node] ✓ 필수 정보 수집 완료 - Summary 생성 및 다음 단계로 진행")
                print(f"[Intake Node] 필드 수집 상태: {field_status}")
            else:
                # 검증 실패: Summary 생성하지 않음
                print(f"[Intake Node] ⚠ 필수 정보 수집 미완료 - Summary 생성 중단")
                print(f"[Intake Node] 필드 수집 상태: {field_status}")
                if missing_fields:
                    print(f"[Intake Node] Summary에서 누락된 필드: {missing_fields}")
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

