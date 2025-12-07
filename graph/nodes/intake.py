import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_gemini
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
    existing_intake_summary = state.get('intake_summary_report', '')  # Re-Intake 모드에서 기존 Summary 보존
    
    # 3. 프롬프트 및 컨텍스트 로드 (매번 새로 로드)
    print(f"[Intake Node] 프롬프트 및 컨텍스트 파일 로드 시작...")
    
    # Re-Intake 모드일 때는 re_intake 프롬프트 사용
    if is_re_intake:
        base_prompt = load_prompt_from_file("stage1_re_intake.md")
        if not base_prompt:
            base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
            print(f"[Intake Node] ⚠ 프롬프트 파일 로드 실패: stage1_re_intake.md")
        else:
            print(f"[Intake Node] ✓ Re-Intake 프롬프트 로드 완료: stage1_re_intake.md ({len(base_prompt)} 문자)")
    else:
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

## 필수 필드 수집 상태 확인 (매우 중요!)
**반드시 다음 5가지 필수 필드가 모두 충분히 수집되었는지 확인하세요:**
1. **주요_증상** (Chief Complaint): 사용자가 상담을 요청한 이유, 현재 기분, 증상의 구체적 내용 (증상의 종류, 강도, 시작 시기, 지속 기간, 악화/완화 요인, 일상생활에 미치는 영향 등 상세한 정보)
   - **매우 중요**: 주요증상은 반드시 완전한 문장으로 기록해야 합니다!
   - "우울", "불안" 같은 단어만 쓰지 마세요!
   - "무엇 때문에 우울한지", "어떤 상황에서 불안한지" 등 원인과 맥락을 포함한 완전한 문장으로 기록하세요!
   - 예시:
     * ❌ 잘못된 예: "우울"
     * ✅ 올바른 예: "최근 직장에서의 스트레스 때문에 우울한 기분이 지속되고 있습니다"
     * ❌ 잘못된 예: "불안"
     * ✅ 올바른 예: "시험 기간이 다가오면서 불안감이 심해져서 집중이 잘 안 됩니다"
   - 주요증상은 사용자가 상담을 요청한 이유와 현재 기분을 파악할 수 있을 정도의 설명이면 충분합니다.
   - 너무 짧은 답변(예: "안 좋아요", "우울해요")만 아니면, 사용자가 자연스럽게 말한 내용을 그대로 수집하면 됩니다.
   - 불필요하게 반복 질문하지 말고, 사용자의 답변에 자연스럽게 공감하며 필요한 핵심 정보만 수집하세요.
2. **수면** (Sleep): 수면 문제 유형 - 사용자의 답변을 `<context_stage1_intake.json>`의 `problem_types` 목록에서 바로 선택
   - 한 번 질문하고 사용자가 답변하면, 정해진 목록 중 하나로 바로 분류하세요
   - 추가 질문 없이 한 번의 답변으로 충분합니다
   - 허용된 유형: "불면증(insomnia)", "과다수면(hypersomnia)", "입면 곤란(difficulty falling asleep)", "수면 유지 곤란(difficulty staying asleep)", "이른 아침 각성(early morning awakening)", "문제 없음"

3. **식욕_체중** (Appetite & Weight): 식욕/체중 변화 - 사용자의 답변을 `<context_stage1_intake.json>`의 `problem_types` 목록에서 바로 선택
   - 한 번 질문하고 사용자가 답변하면, 정해진 목록 중 하나로 바로 분류하세요
   - 추가 질문 없이 한 번의 답변으로 충분합니다
   - 허용된 유형: "식욕 감소(decreased appetite)", "식욕 증가(increased appetite)", "현저한 체중 감소(significant weight loss)", "현저한 체중 증가(significant weight gain)", "문제 없음"

4. **활력_에너지** (Energy & Vitality): 에너지 수준 - 사용자의 답변을 `<context_stage1_intake.json>`의 `problem_types` 목록에서 바로 선택
   - 한 번 질문하고 사용자가 답변하면, 정해진 목록 중 하나로 바로 분류하세요
   - 추가 질문 없이 한 번의 답변으로 충분합니다
   - 허용된 유형: "피로(fatigue)", "활력 상실(loss of energy)", "정신운동 지연(psychomotor retardation)", "정신운동 초조(psychomotor agitation)", "집중력 감소(diminished ability to concentrate)", "우유부단(indecisiveness)", "문제 없음"

5. **신체증상** (Somatic Symptoms): 신체적 불편함 - 사용자의 답변을 `<context_stage1_intake.json>`의 `problem_types` 목록에서 바로 선택
   - 한 번 질문하고 사용자가 답변하면, 정해진 목록 중 하나로 바로 분류하세요
   - 추가 질문 없이 한 번의 답변으로 충분합니다
   - 허용된 유형: "두통(headache)", "위장 증상(gastrointestinal symptoms)", "근육 긴장(muscle tension)", "심계항진(palpitations)", "호흡곤란(shortness of breath)", "흉부 불편감(chest discomfort)", "현기증(dizziness)", "이인증(depersonalization)", "비현실감(derealization)", "문제 없음"

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

**카테고리 기록 형식 (매우 중요! DSM-5 임베딩 성능을 위해 필수!)**:
- 주요_증상: 자유 텍스트 (사용자가 상담을 요청한 이유와 현재 기분을 파악할 수 있는 정도)
  - **매우 중요**: 주요증상은 반드시 완전한 문장으로 기록해야 합니다!
  - "우울", "불안" 같은 단어만 쓰지 마세요!
  - "무엇 때문에 우울한지", "어떤 상황에서 불안한지" 등 원인과 맥락을 포함한 완전한 문장으로 기록하세요!
  - 예시:
    * ❌ 잘못된 예: "우울"
    * ✅ 올바른 예: "최근 직장에서의 스트레스 때문에 우울한 기분이 지속되고 있습니다"
    * ❌ 잘못된 예: "불안"
    * ✅ 올바른 예: "시험 기간이 다가오면서 불안감이 심해져서 집중이 잘 안 됩니다"

**수면, 식욕_체중, 활력_에너지, 신체증상 필드 질문 규칙 (매우 중요!):**
- 각 카테고리는 **한 번만 질문**하고, 사용자가 답변하면 바로 `<context_stage1_intake.json>`의 `problem_types` 목록에서 선택하세요!
- 추가 질문하지 마세요! 사용자의 답변을 받으면 바로 분류하고 다음 필드로 넘어가세요!
- 각 카테고리는 정해진 목록에서 선택만 하면 되므로, 꼬치꼬치 물어볼 필요가 전혀 없습니다!
- 예: 
  * 사용자가 "잠을 잘 못 잤어요"라고 하면 → "불면증(insomnia)" 또는 "입면 곤란"으로 바로 분류하고 추가 질문 금지!
  * 사용자가 "밥을 잘 안 먹어요"라고 하면 → "식욕 감소(decreased appetite)"로 바로 분류하고 추가 질문 금지!
  * 사용자가 "매우 피곤해요"라고 하면 → "피로(fatigue)"로 바로 분류하고 추가 질문 금지!
  * 사용자가 "가슴이 두근거려요"라고 하면 → "심계항진(palpitations)"로 바로 분류하고 추가 질문 금지!
- 비슷한 의미라도 목록에 없는 용어는 절대로 사용하지 마세요!
- 각 카테고리는 배열 형식으로 여러 유형을 기록할 수 있습니다 (예: ["불면증(insomnia)", "수면 유지 곤란"])
- 문제가 없다면 반드시 "문제 없음"으로 기록하세요.

**Summary String 형식 예시:**
```
주요_증상: [사용자가 상담을 요청한 이유와 현재 기분에 대한 설명]
수면: ["불면증(insomnia)", "입면 곤란(difficulty falling asleep)"]
식욕_체중: ["식욕 감소(decreased appetite)"]
활력_에너지: ["피로(fatigue)", "집중력 감소(diminished ability to concentrate)"]
신체증상: ["심계항진(palpitations)"]
```

**주요_증상 필드 수집 기준 (매우 중요!)**:
- 주요증상은 사용자가 상담을 요청한 이유와 현재 기분을 파악할 수 있을 정도면 충분합니다.
- 너무 짧은 답변(예: "안 좋아요")만 아니면, 사용자가 자연스럽게 말한 내용을 그대로 수집하면 됩니다.
- 불필요하게 많은 질문을 반복하지 말고, 사용자의 답변에 자연스럽게 공감하며 핵심 정보만 수집하세요.
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
                                print(f"[Intake Node] ✓ 기존 주요_증상 보존: {existing_chief_complaint[:50]}...")
                                break
                        summary_content = '\n'.join(new_summary_lines)
                
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

