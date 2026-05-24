from __future__ import annotations

"""
RAIS Human Core v3
- 기존 rais_human_core_v1을 보존하면서 AI 분석 보조 레이어를 추가한 V3 엔진
- UI(index.html)는 수정하지 않는 것을 전제로 설계
- app.py에서는 import만 아래처럼 교체하면 됨

from rais_human_core_v3 import (
    normalize_input_data,
    build_ra_result,
    post_process_result,
    build_fallback_result,
)

핵심 원칙:
1. RAIS 내부 계산 결과가 최종 기준이다.
2. AI는 단순 설명자가 아니라 RAIS 판단을 검토·보정하는 보조 판단자이다.
3. AI 응답이 없거나 오류가 나면 v1 결과로 안전하게 fallback한다.
4. 과거 경험 패턴은 미래 예측 분석의 핵심 자료로 prompt에 포함한다.
5. AI가 결론을 바꾸더라도 RAIS 점수 구조를 급격히 흔들지 않고 보수적으로 반영한다.
"""

from dataclasses import asdict
from typing import Any, Dict, List
import json
import os
import re
import traceback

# =========================================================
# 0. 기존 v1 엔진 import
# =========================================================
from rais_engine import rais_human_core_v1 as v1

# app.py가 기존과 같은 이름으로 import할 수 있도록 재노출
normalize_input_data = v1.normalize_input_data
post_process_result = v1.post_process_result

try:
    build_fallback_result = v1.build_fallback_result
except AttributeError:
    def build_fallback_result(input_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        input_data = input_data or {}
        return {
            "engine": "RAIS_HUMAN_CORE_V3_FALLBACK",
            "name": input_data.get("name", "사용자"),
            "one_line_summary": "분석 결과를 생성하지 못했습니다.",
            "current_status_text": "입력은 정상적으로 들어왔지만 결과 생성 단계에서 문제가 발생했습니다.",
            "core_problem_text": "입력 상태 또는 엔진 계산 과정을 다시 점검할 필요가 있습니다.",
            "future_flow_text": "normalize_input_data와 build_ra_result의 연결 상태를 먼저 확인해 주세요.",
            "talent_analysis_text": "",
            "current_fit_text": "",
            "recommended_jobs_text": "",
            "nature_change_text": "",
            "common_comment_text": "이 결과는 참고용입니다.",
        }


MODEL_VERSION = "RAIS_HUMAN_CORE_V3_AI_RA_BALANCED_B_LAYER_2026_05_05"


# =========================================================
# 1. 공통 유틸
# =========================================================
def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def safe_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [safe_text(x) for x in value if safe_text(x)]
    if isinstance(value, tuple):
        return [safe_text(x) for x in value if safe_text(x)]
    if isinstance(value, set):
        return [safe_text(x) for x in value if safe_text(x)]
    text = safe_text(value)
    if not text:
        return []
    return [x.strip() for x in re.split(r"[,/\n]", text) if x.strip()]


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo


def avg(values: List[float], default: float = 50.0) -> float:
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except Exception:
            pass
    if not nums:
        return default
    return sum(nums) / len(nums)


def score_to_label(score: float) -> str:
    score = clamp(score)
    if score > 85:
        return "매우 안정"
    if score >= 65:
        return "안정"
    if score >= 35:
        return "다소 안정"
    if score >= 15:
        return "다소 불안정"
    return "매우 불안정"


def compact_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


def normalize_vector_list(items: Any, default_factor: str) -> List[Dict[str, Any]]:
    """
    AI 결과 또는 v1 결과를 graph에서 읽기 쉬운 vector 구조로 통일.
    """
    result: List[Dict[str, Any]] = []

    if isinstance(items, list):
        for i, item in enumerate(items):
            if isinstance(item, dict):
                factor = safe_text(item.get("factor") or item.get("name") or item.get("title") or default_factor)
                score = clamp(item.get("score", 55), 0, 100)
                rationale = safe_text(item.get("rationale") or item.get("reason") or item.get("text") or "")
                result.append({
                    "factor": factor or f"{default_factor} {i + 1}",
                    "score": round(score, 1),
                    "rationale": rationale,
                })
            else:
                text = safe_text(item)
                if text:
                    result.append({
                        "factor": text[:24],
                        "score": 55.0,
                        "rationale": text,
                    })

    elif isinstance(items, str):
        lines = [x.strip("-• 0123456789.").strip() for x in items.splitlines() if x.strip()]
        for i, line in enumerate(lines[:5]):
            result.append({
                "factor": line[:24] or f"{default_factor} {i + 1}",
                "score": 55.0,
                "rationale": line,
            })

    return result[:5]


# =========================================================
# 2. RA 구조 생성
# =========================================================
def build_ra_structure(input_data: Dict[str, Any], base_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    v1 계산 결과와 정규화 입력을 AI prompt에 넣기 좋은 RA 구조로 정리.
    """

    data = normalize_input_data(input_data)

    root_state = base_result.get("root_state", {})
    if not isinstance(root_state, dict):
        try:
            root_state = asdict(root_state)
        except Exception:
            root_state = {}

    path_distribution = base_result.get("path_distribution", {})
    if not isinstance(path_distribution, dict):
        path_distribution = {}

    path_decision = base_result.get("path_decision", {})
    if not isinstance(path_decision, dict):
        path_decision = {"final_decision": safe_text(path_decision)}

    structure = {
        "model": "Origin → Root → Sub Objects(HW/SW/Environment/Experience)",
        "output_language": data.get("lang") or data.get("language") or data.get("ui_lang") or "ko",
        "name": data.get("name", "사용자"),
        "basic": {
            "name": data.get("name", "사용자"),
            "gender": data.get("gender", ""),
            "age": data.get("age", ""),
            "life_stage": data.get("life_stage", ""),
            "current_job": data.get("current_job", ""),
        },
        "origin": {
            "essences": data.get("essences", []),
        },
        "root": {
            "natures": data.get("natures", []),
            "root_score": base_result.get("root_score", 50),
            "root_state": root_state,
            "alignment_overview": base_result.get("alignment_overview", {}),
            "origin_root_alignment": base_result.get("origin_root_alignment", ""),
            "conflicts": base_result.get("conflicts", []),
        },
        "sub_objects": {
            "hw_score": base_result.get("hw_score", 50),
            "sw_score": base_result.get("sw_score", 50),
            "environment_score": base_result.get("environment_score", 50),
            "experience_score": base_result.get("experience_score", 50),
        },
        "current_context": {
            "current_status": data.get("current_status", {}),
            "execution": data.get("execution", {}),
            "current_goals": data.get("current_goals", []),
            "current_goal_1": data.get("current_goal_1", ""),
            "current_goal_2": data.get("current_goal_2", ""),
            "current_goal_3": data.get("current_goal_3", ""),
            "concern": data.get("concern", ""),
        },
        "experience_patterns": extract_experience_patterns(data),
        "v1_judgement": {
            "one_line_summary": base_result.get("one_line_summary", ""),
            "current_status_text": base_result.get("current_status_text", ""),
            "core_problem_text": base_result.get("core_problem_text", ""),
            "future_flow_text": base_result.get("future_flow_text", ""),
            "path_distribution": path_distribution,
            "path_decision": path_decision,
            "threat_vectors": base_result.get("threat_vectors", []),
            "opportunity_vectors": base_result.get("opportunity_vectors", []),
            "talent_axis_scores": base_result.get("talent_axis_scores", {}),
            "current_job_fit": base_result.get("current_job_fit", {}),
            "recommended_axes": base_result.get("recommended_axes", []),
        },
    }

    return structure


def extract_experience_patterns(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    과거 경험 패턴을 AI 분석용으로 정리.
    UI가 experience_job[], experience_result[], experience_reason[] 형태를 쓰거나
    v1 normalize 결과의 experience dict를 쓰는 경우를 모두 받아들인다.
    """
    raw_exp = data.get("experience", {})
    patterns: Dict[str, Any] = {
        "summary": "",
        "items": [],
        "success_keywords": [],
        "failure_keywords": [],
        "risk_repetition": [],
        "future_hint": "",
    }

    if isinstance(raw_exp, dict):
        patterns["raw"] = raw_exp

        for key, val in raw_exp.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        patterns["items"].append(item)
                    elif safe_text(item):
                        patterns["items"].append({"text": safe_text(item)})
            elif isinstance(val, dict):
                patterns["items"].append({key: val})
            elif safe_text(val):
                patterns["items"].append({key: safe_text(val)})

        # 점수형 experience도 해석 보조에 사용
        score_keys = ["success", "failure_recovery", "consistency", "trust", "성공 경험", "실패 회복", "지속 경험", "자기 신뢰"]
        score_bits = []
        for k in score_keys:
            if k in raw_exp:
                score_bits.append(f"{k}: {raw_exp.get(k)}")
        if score_bits:
            patterns["summary"] = ", ".join(score_bits)

    elif isinstance(raw_exp, list):
        patterns["items"] = raw_exp
        patterns["raw"] = raw_exp
    elif safe_text(raw_exp):
        patterns["summary"] = safe_text(raw_exp)
        patterns["raw"] = safe_text(raw_exp)
    else:
        patterns["raw"] = {}

    # 단순 반복 원인 추출
    reason_counter: Dict[str, int] = {}
    for item in patterns["items"]:
        if not isinstance(item, dict):
            continue
        reason = safe_text(
            item.get("reason")
            or item.get("주된 이유")
            or item.get("이유")
            or item.get("메모")
            or item.get("note")
        )
        result = safe_text(
            item.get("result")
            or item.get("성과")
            or item.get("결과")
        )

        if reason:
            reason_counter[reason] = reason_counter.get(reason, 0) + 1

        if result in ["성공", "안정", "좋음"]:
            patterns["success_keywords"].append(reason or result)
        elif result in ["실패", "사퇴", "중단", "악화"]:
            patterns["failure_keywords"].append(reason or result)

    patterns["risk_repetition"] = [
        k for k, v in sorted(reason_counter.items(), key=lambda x: x[1], reverse=True)
        if v >= 2
    ]

    if patterns["risk_repetition"]:
        patterns["future_hint"] = "반복된 과거 문제 원인은 미래 예측에서 주요 위협 요인으로 반영됩니다."
    elif patterns["items"] or patterns["summary"]:
        patterns["future_hint"] = "과거 경험은 현재 선택의 적합성과 미래 흐름 판단에 참고됩니다."
    else:
        patterns["future_hint"] = "과거 경험 정보가 부족하므로, 미래 예측은 현재 본질·본성·환경 중심으로 해석합니다."

    return patterns


# =========================================================
# 3. AI Prompt 생성
# =========================================================
def build_ai_prompt(ra_structure: Dict[str, Any], output_language: str = "ko") -> str:
    """
    RA 구조를 AI 분석용 prompt로 변환.
    V3에서는 AI가 단순 설명자가 아니라 RAIS v1 판단을 검토하고,
    보수적인 수정/보완 의견을 JSON으로 제시하도록 요구한다.
    """

    name = ra_structure.get("name", "사용자")
    basic = ra_structure.get("basic", {})
    origin = ra_structure.get("origin", {})
    root = ra_structure.get("root", {})
    sub = ra_structure.get("sub_objects", {})
    ctx = ra_structure.get("current_context", {})
    exp = ra_structure.get("experience_patterns", {})
    v1j = ra_structure.get("v1_judgement", {})

    output_language = (output_language or ra_structure.get("output_language") or "ko").lower()
    if output_language.startswith("en"):
        language_instruction = (
            "[Output Language]\n"
            "- Write all user-facing JSON text fields in natural English.\n"
            "- Keep machine classification labels in Korean only where the JSON schema explicitly requires one of these values: "
            "개선 흐름, 유지 흐름, 위협 흐름, 개선 권장, 유지 권장, 위협 관리, 혼합 상태.\n"
            "- Do not use stiff literal translations such as behavior connection; prefer natural phrases such as nature-flow adjustment, practical alignment, execution conditions, and future tendency.\n"
        )
    else:
        language_instruction = (
            "[출력 언어]\n"
            "- 사용자에게 보이는 JSON 텍스트는 자연스러운 한국어로 작성하세요.\n"
        )

    prompt = f"""
당신은 RAIS Human Core V3의 보조 판단 엔진입니다.
AI의 역할은 단순한 설명이 아니라, RAIS v1 판단을 구조적으로 검토하고 필요한 경우 보수적으로 보정 의견을 제시하는 것입니다.
최종 출력은 RAIS가 다시 정렬하므로, AI는 아래 JSON 형식으로만 판단 재료를 제공해야 합니다.

{language_instruction}
[절대 원칙]
- RAIS v1을 무조건 뒤집지 마세요.
- 단, 입력 데이터·과거 경험·환경 조건을 볼 때 v1 판단이 약하거나 빠뜨린 부분이 있으면 명확히 지적하세요.
- 결론을 바꿀 필요가 있으면 "override_needed"를 true로 하고, 이유와 신뢰도를 제시하세요.
- 신뢰도(confidence)는 0~100입니다. 단, 유효한 보완 의견이 있으면 30 미만으로 두지 마세요.
- adjustment_strength도 0~100입니다. 경로 보정 의견이 있으면 20 미만으로 두지 마세요.
- dominant_flow는 반드시 "개선 흐름", "유지 흐름", "위협 흐름" 중 하나를 선택하세요. 혼합이라도 가장 강한 방향 하나를 고르세요.
- 표현은 일상어로 쓰고, '발현' 대신 '살아나는 방식', '연결되는 방식'을 사용하세요.
- 의학/법률/투자 판단처럼 확정적으로 쓰지 마세요.

[분석 대상]
이름: {basic.get("name", name)}
성별: {basic.get("gender", "")}
연령/생애단계: {basic.get("age", "")} / {basic.get("life_stage", "")}
현재 직업/상태: {basic.get("current_job", "")}

[RA 기본 구조]
모델: Origin → Root → Sub Objects(HW/SW/Environment/Experience)

[Origin Object: 본질]
선택 본질: {", ".join(safe_list(origin.get("essences")))}

[Root Object: 현재 본성 및 근본 상태]
현재 본성: {", ".join(safe_list(root.get("natures")))}
Root Score: {root.get("root_score")}
Root State:
{compact_json(root.get("root_state", {}))}

본질-본성 정렬:
{compact_json(root.get("alignment_overview", {}))}

상충/충돌 요소:
{compact_json(root.get("conflicts", []))}

[Sub Objects]
HW/건강 기반: {sub.get("hw_score")}
SW/실행·인지 기반: {sub.get("sw_score")}
환경 기반: {sub.get("environment_score")}
경험 기반: {sub.get("experience_score")}

[현재 맥락]
현재 상태:
{compact_json(ctx.get("current_status", {}))}

실행 조건:
{compact_json(ctx.get("execution", {}))}

현재 목표: {ctx.get("goal", ctx.get("current_goal_1", ""))}
현재 고민: {ctx.get("concern", ctx.get("current_goal_2", ""))}

[과거 경험 패턴 - 미래 예측에 반드시 반영]
경험 요약: {exp.get("summary", "")}
경험 항목:
{compact_json(exp.get("items", []))}
성공 관련 단서: {", ".join(safe_list(exp.get("success_keywords")))}
실패/중단 관련 단서: {", ".join(safe_list(exp.get("failure_keywords")))}
반복 위험 원인: {", ".join(safe_list(exp.get("risk_repetition")))}
경험 기반 예측 힌트: {exp.get("future_hint", "")}

[RAIS v1 내부 판단 - 반드시 검토 대상]
한 줄 요약: {v1j.get("one_line_summary", "")}
현재 상태: {v1j.get("current_status_text", "")}
핵심 문제: {v1j.get("core_problem_text", "")}
미래 흐름: {v1j.get("future_flow_text", "")}
경로 분포:
{compact_json(v1j.get("path_distribution", {}))}
경로 판단:
{compact_json(v1j.get("path_decision", {}))}
위협 벡터:
{compact_json(v1j.get("threat_vectors", []))}
기회 벡터:
{compact_json(v1j.get("opportunity_vectors", []))}
재능 축:
{compact_json(v1j.get("talent_axis_scores", {}))}
현재 직업 적합:
{compact_json(v1j.get("current_job_fit", {}))}

[AI가 반드시 수행할 일]
1. RAIS v1 판단에 동의하는 부분과 보완해야 할 부분을 구분하세요.
2. 과거 경험 패턴이 미래 흐름을 개선/유지/위협 중 어디로 밀어주는지 판단하세요.
3. 현재 목표와 현실 조건이 충돌하는 지점을 찾으세요.
4. 필요하면 v1의 dominant flow를 보수적으로 조정할 의견을 내세요.
5. 최종 사용자가 읽을 핵심 문제·미래 흐름·행동 조정 문장을 작성하세요.

아래 JSON 형식으로만 답하세요. 설명 문장, 코드블록, markdown을 쓰지 마세요.

{{
  "judgement_review": {{
    "agree_with_v1": "v1 판단 중 타당한 부분 1~2문장",
    "missing_points": "v1 판단에서 약하거나 빠진 부분 1~2문장",
    "disagreement": "v1과 다르게 볼 수 있는 부분. 없으면 빈 문자열",
    "override_needed": false,
    "override_reason": "보정이 필요한 이유. 없으면 빈 문자열",
    "confidence": 30
  }},
  "core_problem": "핵심 문제를 일상어로 2~3문장",
  "future_prediction": "과거 경험 패턴과 현재 상태를 함께 반영한 미래 흐름 3~5문장",
  "strategy": "지금 필요한 행동 조정 방향 3~5문장",
  "risk_factors": [
    {{"factor": "위험요인명", "score": 0, "rationale": "이유"}}
  ],
  "opportunity_factors": [
    {{"factor": "기회요인명", "score": 0, "rationale": "이유"}}
  ],
  "experience_interpretation": "과거 경험이 미래 예측에 주는 의미 2~4문장",
  "path_adjustment": {{
    "dominant_flow": "개선 흐름/유지 흐름/위협 흐름 중 하나. 혼합이어도 가장 강한 쪽 하나를 고르세요",
    "suggested_final_decision": "개선 권장/유지 권장/위협 관리/혼합 상태 중 하나",
    "adjustment_strength": 20,
    "reason": "경로 보정 이유"
  }},
  "ra_mapping_hint": {{
    "root_change": "Root 변화 방향",
    "essence_nature_link": "본질과 본성 연결 해석",
    "correction_needed": "RAIS 보정이 필요한 부분"
  }}
}}
""".strip()

    return prompt

# =========================================================
# 4. AI 호출
# =========================================================
def call_ai_analysis(prompt: str) -> str:
    """
    OpenAI API 호출.
    - OPENAI_API_KEY가 없으면 빈 문자열 반환 → v1 fallback.
    - 로컬 테스트 안정성을 위해 오류를 밖으로 던지지 않는다.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    # print("DEBUG AI CALL ENTERED")
    # print("DEBUG OPENAI_API_KEY EXISTS:", bool(api_key))
    # print("DEBUG PROMPT LENGTH:", len(prompt))

    if not api_key:
        # print("DEBUG AI SKIPPED: OPENAI_API_KEY 없음")
        return ""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        model = os.getenv("RAIS_AI_MODEL", "gpt-4.1-mini")
        # print("DEBUG AI MODEL:", model)

        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 RAIS Human Core V3의 보조 판단 엔진입니다. "
                        "반드시 유효한 JSON 객체만 출력하세요."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or ""

        # print("DEBUG AI RESPONSE LENGTH:", len(content))
        # print("DEBUG AI RESPONSE HEAD:", content[:300])

        return content

    except Exception:
        # print("RAIS V3 AI call error:")
        traceback.print_exc()
        return ""

# =========================================================
# 5. AI 응답 분해
# =========================================================
def parse_ai_result(text: str) -> Dict[str, Any]:
    """
    AI 응답을 전략 / 문제 / 방향 / 예측 요소로 분해.
    V3 JSON 구조와 구버전 JSON 구조를 모두 받아들인다.
    JSON 실패 시 텍스트 기반 fallback.
    """
    text = safe_text(text)
    if not text:
        return {
            "available": False,
            "core_problem": "",
            "future_prediction": "",
            "strategy": "",
            "risk_factors": [],
            "opportunity_factors": [],
            "experience_interpretation": "",
            "judgement_review": {},
            "path_adjustment": {},
            "ra_mapping_hint": {},
            "raw_text": "",
        }

    cleaned = text.strip()

    # ```json ... ``` 방지
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("AI JSON root is not dict")

        judgement_review = parsed.get("judgement_review", {})
        if not isinstance(judgement_review, dict):
            judgement_review = {}

        path_adjustment = parsed.get("path_adjustment", {})
        if not isinstance(path_adjustment, dict):
            path_adjustment = {}

        ra_mapping_hint = parsed.get("ra_mapping_hint", {})
        if not isinstance(ra_mapping_hint, dict):
            ra_mapping_hint = {}

        return {
            "available": True,
            "core_problem": safe_text(parsed.get("core_problem")),
            "future_prediction": safe_text(parsed.get("future_prediction")),
            "strategy": safe_text(parsed.get("strategy")),
            "risk_factors": normalize_vector_list(parsed.get("risk_factors", []), "AI 위험 요인"),
            "opportunity_factors": normalize_vector_list(parsed.get("opportunity_factors", []), "AI 기회 요인"),
            "experience_interpretation": safe_text(parsed.get("experience_interpretation")),
            "judgement_review": judgement_review,
            "path_adjustment": path_adjustment,
            "ra_mapping_hint": ra_mapping_hint,
            "raw_text": text,
        }

    except Exception:
        # JSON 파싱 실패 시 최소 구조로 보존
        return {
            "available": True,
            "core_problem": extract_loose_section(cleaned, ["핵심 문제", "core_problem"]),
            "future_prediction": extract_loose_section(cleaned, ["미래", "future_prediction", "예측"]),
            "strategy": extract_loose_section(cleaned, ["전략", "strategy", "방향"]),
            "risk_factors": normalize_vector_list(extract_loose_section(cleaned, ["위험", "risk"]), "AI 위험 요인"),
            "opportunity_factors": normalize_vector_list(extract_loose_section(cleaned, ["기회", "opportunity"]), "AI 기회 요인"),
            "experience_interpretation": extract_loose_section(cleaned, ["경험", "experience"]),
            "judgement_review": {},
            "path_adjustment": {},
            "ra_mapping_hint": {},
            "raw_text": text,
        }

def extract_loose_section(text: str, keys: List[str]) -> str:
    lines = text.splitlines()
    selected = []
    capture = False

    for line in lines:
        plain = line.strip()
        if not plain:
            continue

        if any(k.lower() in plain.lower() for k in keys):
            capture = True
            selected.append(plain)
            continue

        if capture:
            if re.match(r"^\s*(#+|\d+\.|\[.+\]|[가-힣A-Za-z ]+:)\s*", plain) and len(selected) >= 2:
                break
            selected.append(plain)

        if len(selected) >= 6:
            break

    return "\n".join(selected).strip()


# =========================================================
# 6. RA 구조 매핑
# =========================================================
def map_to_ra_structure(parsed: Dict[str, Any], ra_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI 응답을 Root 변화, 영향 흐름, 본질-본성 연결로 재구성.
    """
    if not parsed.get("available"):
        return {
            "available": False,
            "root_change": "",
            "dominant_flow": "",
            "essence_nature_link": "",
            "correction_needed": "",
            "ai_threat_vectors": [],
            "ai_opportunity_vectors": [],
            "ai_core_problem": "",
            "ai_future_prediction": "",
            "ai_strategy": "",
            "ai_experience_interpretation": "",
            "judgement_review": {},
            "path_adjustment": {},
        }

    hint = parsed.get("ra_mapping_hint", {})
    if not isinstance(hint, dict):
        hint = {}

    path_adjustment = parsed.get("path_adjustment", {})
    if not isinstance(path_adjustment, dict):
        path_adjustment = {}

    judgement_review = parsed.get("judgement_review", {})
    if not isinstance(judgement_review, dict):
        judgement_review = {}

    mapped = {
        "available": True,
        "root_change": safe_text(hint.get("root_change")),
        "dominant_flow": safe_text(path_adjustment.get("dominant_flow") or hint.get("dominant_flow")),
        "essence_nature_link": safe_text(hint.get("essence_nature_link")),
        "correction_needed": safe_text(hint.get("correction_needed")),
        "ai_threat_vectors": parsed.get("risk_factors", []),
        "ai_opportunity_vectors": parsed.get("opportunity_factors", []),
        "ai_core_problem": parsed.get("core_problem", ""),
        "ai_future_prediction": parsed.get("future_prediction", ""),
        "ai_strategy": parsed.get("strategy", ""),
        "ai_experience_interpretation": parsed.get("experience_interpretation", ""),
        "judgement_review": judgement_review,
        "path_adjustment": path_adjustment,
        "raw_ai": parsed.get("raw_text", ""),
    }

    return mapped

# =========================================================
# 7. RAIS 보정/통합
# =========================================================
def integrate_ai_results(
    mapped_data: Dict[str, Any],
    ra_structure: Dict[str, Any],
    base_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    AI 분석 결과와 RAIS 내부 판단을 통합·정렬.
    V3에서는 AI가 단순 문장 보조가 아니라 경로 판단과 핵심 문제를
    제한적으로 보정할 수 있다. 단, RAIS 안정성을 위해 보정 폭은 작게 제한한다.
    """
    integrated = dict(base_result)
    integrated["engine"] = MODEL_VERSION
    integrated["v2_enabled"] = True
    integrated["ai_used"] = bool(mapped_data.get("available"))

    if not mapped_data.get("available"):
        integrated["ai_note"] = "OPENAI_API_KEY가 없거나 AI 응답이 없어 v1 결과를 기준으로 출력했습니다."
        integrated["engine"] = MODEL_VERSION + "_NO_AI_FALLBACK"
        return integrated

    # v1 vector + AI vector를 섞되, v1을 우선한다.
    base_threats = normalize_vector_list(base_result.get("threat_vectors", []), "위협 요인")
    ai_threats = normalize_vector_list(mapped_data.get("ai_threat_vectors", []), "AI 위험 요인")

    base_opps = normalize_vector_list(base_result.get("opportunity_vectors", []), "기회 요인")
    ai_opps = normalize_vector_list(mapped_data.get("ai_opportunity_vectors", []), "AI 기회 요인")

    integrated["threat_vectors"] = merge_vectors(base_threats, ai_threats, max_items=5)
    integrated["opportunity_vectors"] = merge_vectors(base_opps, ai_opps, max_items=5)

    integrated["ai_core_problem"] = mapped_data.get("ai_core_problem", "")
    integrated["ai_future_prediction"] = mapped_data.get("ai_future_prediction", "")
    integrated["ai_strategy"] = mapped_data.get("ai_strategy", "")
    integrated["ai_experience_interpretation"] = mapped_data.get("ai_experience_interpretation", "")
    integrated["ai_judgement_review"] = mapped_data.get("judgement_review", {})
    integrated["ai_path_adjustment"] = mapped_data.get("path_adjustment", {})
    integrated["ai_ra_mapping"] = {
        "root_change": mapped_data.get("root_change", ""),
        "dominant_flow": mapped_data.get("dominant_flow", ""),
        "essence_nature_link": mapped_data.get("essence_nature_link", ""),
        "correction_needed": mapped_data.get("correction_needed", ""),
    }

    # 과거 경험 해석을 별도 보존
    integrated["experience_pattern_text"] = mapped_data.get("ai_experience_interpretation", "")

    # AI 판단 영향도 계산 및 보수적 경로 보정
    influence = compute_ai_influence(mapped_data)
    integrated["ai_influence_score"] = influence

    adjusted_distribution, adjustment_note = adjust_path_distribution_with_ai(
        base_result.get("path_distribution", {}),
        mapped_data,
        influence,
    )
    if adjusted_distribution:
        integrated["path_distribution"] = adjusted_distribution

    adjusted_decision = adjust_path_decision_with_ai(
        base_result.get("path_decision", {}),
        mapped_data,
        adjusted_distribution or base_result.get("path_distribution", {}),
        influence,
    )
    if adjusted_decision:
        integrated["path_decision"] = adjusted_decision

    integrated["ai_adjustment_note"] = adjustment_note

    return integrated

def merge_vectors(base: List[Dict[str, Any]], ai: List[Dict[str, Any]], max_items: int = 5) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    def add(item: Dict[str, Any], source: str):
        factor = safe_text(item.get("factor"))
        if not factor:
            return
        key = factor.replace(" ", "")
        if key in seen:
            return
        seen.add(key)
        merged.append({
            "factor": factor,
            "score": round(clamp(item.get("score", 55)), 1),
            "rationale": safe_text(item.get("rationale")),
            "source": source,
        })

    for item in base:
        add(item, "RAIS")
    for item in ai:
        add(item, "AI")

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    return merged[:max_items]


def compute_ai_influence(mapped_data: Dict[str, Any]) -> float:
    """
    AI가 RAIS 결과에 어느 정도 영향을 줄지 계산한다.
    B안: AI가 숫자를 0으로 주더라도 보완 의견·경로 의견·위험/기회 벡터가 있으면
    최소 영향도를 추론하여 결과에 작게 반영한다.
    """
    review = mapped_data.get("judgement_review", {})
    if not isinstance(review, dict):
        review = {}
    path_adj = mapped_data.get("path_adjustment", {})
    if not isinstance(path_adj, dict):
        path_adj = {}

    confidence = clamp(review.get("confidence", 0), 0, 100) / 100.0
    strength = clamp(path_adj.get("adjustment_strength", 0), 0, 100) / 100.0

    # AI가 숫자를 0으로 두는 경우를 대비한 추론 보정
    has_review_text = bool(
        safe_text(review.get("missing_points"))
        or safe_text(review.get("disagreement"))
        or safe_text(review.get("override_reason"))
    )
    has_path_text = bool(
        safe_text(path_adj.get("dominant_flow"))
        or safe_text(path_adj.get("suggested_final_decision"))
        or safe_text(path_adj.get("reason"))
    )
    has_vectors = bool(mapped_data.get("ai_threat_vectors") or mapped_data.get("ai_opportunity_vectors"))

    if confidence <= 0 and has_review_text:
        confidence = 0.55
    if strength <= 0 and has_path_text:
        strength = 0.40
    if confidence <= 0 and has_vectors:
        confidence = 0.45
    if strength <= 0 and has_vectors:
        strength = 0.30

    override_needed = bool(review.get("override_needed"))

    base = (confidence * 0.55) + (strength * 0.35)
    if has_review_text:
        base += 0.04
    if has_path_text:
        base += 0.04
    if override_needed:
        base += 0.12

    # 안정성 보존: AI 영향력은 최대 0.45로 제한
    return round(min(base, 0.45), 3)


def avg_vector_score(items: Any) -> float:
    vectors = normalize_vector_list(items, "요인")
    if not vectors:
        return 0.0
    return avg([clamp(x.get("score", 0), 0, 100) for x in vectors], default=0.0)


def infer_dominant_flow(mapped_data: Dict[str, Any], dist: Dict[str, float]) -> str:
    path_adj = mapped_data.get("path_adjustment", {})
    if not isinstance(path_adj, dict):
        path_adj = {}

    dominant = normalize_flow_name(path_adj.get("dominant_flow") or mapped_data.get("dominant_flow"))
    if dominant in ["개선 흐름", "유지 흐름", "위협 흐름"]:
        return dominant

    suggested = safe_text(path_adj.get("suggested_final_decision"))
    if "개선" in suggested:
        return "개선 흐름"
    if "위협" in suggested or "위험" in suggested:
        return "위협 흐름"
    if "유지" in suggested:
        return "유지 흐름"

    risk_avg = avg_vector_score(mapped_data.get("ai_threat_vectors", []))
    opp_avg = avg_vector_score(mapped_data.get("ai_opportunity_vectors", []))
    if risk_avg >= opp_avg + 5 and risk_avg >= 55:
        return "위협 흐름"
    if opp_avg >= risk_avg + 5 and opp_avg >= 55:
        return "개선 흐름"

    # 그래도 모호하면 기존 RAIS 분포의 1순위 유지
    if dist:
        return max(dist, key=dist.get)
    return ""

def normalize_flow_name(flow: Any) -> str:
    text = safe_text(flow)
    if not text:
        return ""
    if "개선" in text and "완만" not in text:
        return "개선 흐름"
    if "유지" in text:
        return "유지 흐름"
    if "위협" in text or "위험" in text:
        return "위협 흐름"
    if "혼합" in text:
        return "혼합 상태"
    return text


def get_distribution_value(distribution: Dict[str, Any], flow: str) -> float:
    if not isinstance(distribution, dict):
        return 0.0
    candidates = {
        "개선 흐름": ["개선 흐름", "개선 경로", "완만 개선"],
        "유지 흐름": ["유지 흐름", "유지 경로"],
        "위협 흐름": ["위협 흐름", "위협 경로", "완만 위협"],
    }.get(flow, [flow])
    total = 0.0
    for k, v in distribution.items():
        key = safe_text(k)
        if key in candidates or any(c in key for c in candidates):
            total += clamp(v, 0, 100)
    return total


def standardize_distribution(distribution: Dict[str, Any]) -> Dict[str, float]:
    """
    v1의 다양한 경로명(개선 경로/완만 개선 등)을 v2 화면용 3축으로 정리한다.
    이미 3축이면 그대로 유지한다.
    """
    if not isinstance(distribution, dict) or not distribution:
        return {"개선 흐름": 33.3, "유지 흐름": 33.4, "위협 흐름": 33.3}

    improve = get_distribution_value(distribution, "개선 흐름")
    maintain = get_distribution_value(distribution, "유지 흐름")
    threat = get_distribution_value(distribution, "위협 흐름")

    if improve + maintain + threat <= 0:
        for k, v in distribution.items():
            key = safe_text(k)
            if "개선" in key:
                improve += clamp(v, 0, 100)
            elif "유지" in key:
                maintain += clamp(v, 0, 100)
            elif "위협" in key or "위험" in key:
                threat += clamp(v, 0, 100)

    total = improve + maintain + threat
    if total <= 0:
        return {"개선 흐름": 33.3, "유지 흐름": 33.4, "위협 흐름": 33.3}

    return {
        "개선 흐름": round(improve / total * 100, 1),
        "유지 흐름": round(maintain / total * 100, 1),
        "위협 흐름": round(threat / total * 100, 1),
    }


def adjust_path_distribution_with_ai(
    base_distribution: Dict[str, Any],
    mapped_data: Dict[str, Any],
    influence: float,
) -> tuple[Dict[str, float], str]:
    """
    AI의 dominant_flow 의견을 경로 분포에 보수적으로 반영한다.
    한 번에 최대 7점 정도만 이동하도록 제한한다.
    """
    dist = standardize_distribution(base_distribution)
    path_adj = mapped_data.get("path_adjustment", {})
    if not isinstance(path_adj, dict):
        path_adj = {}

    dominant = infer_dominant_flow(mapped_data, dist)
    reason = safe_text(path_adj.get("reason"))

    if dominant not in ["개선 흐름", "유지 흐름", "위협 흐름"] or influence <= 0.05:
        return dist, "AI 검토 결과, RAIS 기본 경로 판단을 유지하는 것이 적절합니다."

    # influence 0.45일 때도 최대 약 8점 이동
    shift = round(min(8.0, 18.0 * influence), 1)
    if shift <= 0:
        return dist, "AI 검토 결과, 경로 분포의 수치 조정 없이 해석 보강만 반영했습니다."

    others = [k for k in dist.keys() if k != dominant]
    for k in others:
        reduction = min(dist[k], shift / 2)
        dist[k] = round(dist[k] - reduction, 1)
        dist[dominant] = round(dist[dominant] + reduction, 1)

    # 합계 100 보정
    total = sum(dist.values())
    if total != 100:
        max_key = max(dist, key=dist.get)
        dist[max_key] = round(dist[max_key] + (100 - total), 1)

    note = f"AI 검토를 반영하여 {dominant} 쪽으로 약 {shift}점 이내에서 보수적으로 조정했습니다."
    if reason:
        note += f" 이유: {reason}"
    return dist, note


def decide_from_distribution(distribution: Dict[str, Any]) -> Dict[str, Any]:
    dist = standardize_distribution(distribution)
    ordered = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    top_name, top_score = ordered[0]
    second_name, second_score = ordered[1]

    if top_name == "개선 흐름" and top_score >= 40:
        final = "개선 권장"
    elif top_name == "위협 흐름" and top_score >= 40:
        final = "위협 관리"
    elif top_name == "유지 흐름" and top_score >= 38:
        final = "유지 권장"
    else:
        final = "혼합 상태"

    return {
        "final_decision": final,
        "top_path": {"name": top_name, "score": round(top_score, 1)},
        "second_path": {"name": second_name, "score": round(second_score, 1)},
    }


def adjust_path_decision_with_ai(
    base_decision: Any,
    mapped_data: Dict[str, Any],
    distribution: Dict[str, Any],
    influence: float,
) -> Dict[str, Any]:
    """
    경로 분포를 기준으로 최종 판단명을 정리한다.
    AI suggested_final_decision은 영향도가 충분할 때만 참고한다.
    """
    decision = decide_from_distribution(distribution)
    path_adj = mapped_data.get("path_adjustment", {})
    if not isinstance(path_adj, dict):
        path_adj = {}

    suggested = safe_text(path_adj.get("suggested_final_decision"))
    allowed = ["개선 권장", "유지 권장", "위협 관리", "혼합 상태"]
    if influence >= 0.25 and suggested in allowed:
        decision["final_decision"] = suggested

    if isinstance(base_decision, dict):
        decision["base_final_decision"] = base_decision.get("final_decision", "")
    elif safe_text(base_decision):
        decision["base_final_decision"] = safe_text(base_decision)

    decision["ai_influence_score"] = influence
    return decision



# =========================================================
# 7-1. 출력 언어 보조 함수
# =========================================================
def detect_output_language(input_data: Dict[str, Any]) -> str:
    """
    app.py에서 lang/language/ui_lang 중 하나를 넘겨주면 결과 문장 언어를 결정한다.
    값이 없으면 기존 한국어 결과를 유지한다.
    """
    if not isinstance(input_data, dict):
        return "ko"

    value = (
        input_data.get("lang")
        or input_data.get("language")
        or input_data.get("ui_lang")
        or input_data.get("output_language")
        or "ko"
    )
    value = safe_text(value, "ko").lower()

    if value.startswith("en"):
        return "en"
    return "ko"


def flow_label_en(flow: Any) -> str:
    text = safe_text(flow)
    mapping = {
        "개선 흐름": "improvement tendency",
        "유지 흐름": "maintenance tendency",
        "위협 흐름": "threat tendency",
        "개선 경로": "improvement path",
        "유지 경로": "maintenance path",
        "위협 경로": "threat path",
        "완만 개선": "gradual improvement",
        "완만 위협": "gradual threat",
    }
    for ko, en in mapping.items():
        if ko in text:
            return en
    return text or "undetermined tendency"


def decision_label_en(decision: Any) -> str:
    text = safe_text(decision)
    mapping = {
        "개선 권장": "improvement-oriented adjustment",
        "유지 권장": "maintenance-oriented adjustment",
        "위협 관리": "threat management",
        "혼합 상태": "mixed state",
    }
    return mapping.get(text, text or "mixed state")


def state_label_en(label: Any) -> str:
    text = safe_text(label)
    mapping = {
        "매우 안정": "very stable",
        "안정": "stable",
        "다소 안정": "moderately stable",
        "다소 불안정": "somewhat unstable",
        "매우 불안정": "very unstable",
    }
    return mapping.get(text, text or "moderately stable")


def build_ra_narrative_en(integrated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    English narrative layer for the v3 result page.
    Numeric structures and internal Korean path keys are preserved for charts,
    while user-facing text fields are rewritten in natural English.
    """
    result = dict(integrated_data)

    root_state = result.get("root_state", {}) or {}
    root_score = clamp(result.get("root_score", avg([
        root_state.get("stability", 50),
        root_state.get("drive", 50),
        root_state.get("cognition", 50),
        root_state.get("relation", 50),
    ])))

    path_decision = result.get("path_decision", {})
    if isinstance(path_decision, dict):
        final_decision_ko = safe_text(path_decision.get("final_decision"))
    else:
        final_decision_ko = safe_text(path_decision)

    overall_label = state_label_en(score_to_label(root_score))
    final_decision = decision_label_en(final_decision_ko)

    ai_core = safe_text(result.get("ai_core_problem"))
    ai_future = safe_text(result.get("ai_future_prediction"))
    ai_strategy = safe_text(result.get("ai_strategy"))
    ai_review = result.get("ai_judgement_review", {})
    if not isinstance(ai_review, dict):
        ai_review = {}

    missing = safe_text(ai_review.get("missing_points"))
    disagreement = safe_text(ai_review.get("disagreement"))

    result["one_line_summary"] = (
        f"The current state is {overall_label}. In RAIS's integrated view, "
        f"the priority is to adjust execution conditions and recurring burdens before relying only on existing strengths. "
        f"The final direction is centered on {final_decision}."
    )

    result["current_status_text"] = (
        f"The current root state is interpreted as {overall_label}. "
        "The result should be read as a flow-based diagnosis rather than a fixed personality judgement."
    )

    if ai_core:
        extra = []
        if missing:
            extra.append(f"Another important factor to consider is that {missing}")
        if disagreement:
            extra.append(f"Another possible interpretation is that {disagreement}")
        result["core_problem_text"] = (
            f"{ai_core}\n\n"
            "From the RAIS perspective, this is not simply a personal weakness. "
            "It indicates the point where essence, current nature, and real conditions are not yet fully connected into practical flow."
            + ("\n" + "\n".join(extra) if extra else "")
        )
    else:
        result["core_problem_text"] = (
            "The key issue is not a single defect, but the degree to which essence and current nature are connected to practical action. "
            "Execution conditions and environmental support need to be checked together."
        )

    path_dist = result.get("path_distribution", {})
    try:
        if isinstance(path_dist, str):
            path_dist = json.loads(path_dist)
    except Exception:
        path_dist = {}

    improve = round(float(path_dist.get("개선 흐름", 0)), 1)
    maintain = round(float(path_dist.get("유지 흐름", 0)), 1)
    risk = round(float(path_dist.get("위협 흐름", 0)), 1)

    future_text = []
    future_text.append(
        f"The current flow suggests [{final_decision}]. "
        "Improvement, maintenance, and threat tendencies coexist, but the threat tendency is relatively more visible at this stage. "
        "This suggests that future direction may shift depending on conditions and behavioral patterns."
    )
    future_text.append(
        "In particular, dispersed execution energy and limited environmental conditions can make the threat tendency more prominent."
    )

    flows = [
        ("위협 흐름", risk),
        ("유지 흐름", maintain),
        ("개선 흐름", improve),
    ]
    flows_sorted = sorted(flows, key=lambda x: x[1], reverse=True)

    if len(flows_sorted) >= 1:
        future_text.append(
            f"The primary flow is {flow_label_en(flows_sorted[0][0])} ({flows_sorted[0][1]}%), "
            "which should be considered first."
        )
    if len(flows_sorted) >= 2:
        future_text.append(
            f"The secondary flow is {flow_label_en(flows_sorted[1][0])} ({flows_sorted[1][1]}%), "
            "which also influences the interpretation."
        )
    if len(flows_sorted) >= 3:
        future_text.append(
            f"Reference flow – {flow_label_en(flows_sorted[2][0])} ({flows_sorted[2][1]}%): "
            "this may still affect the result depending on conditions and nature selection."
        )

    if ai_future:
        future_text.append(ai_future)

    result["future_flow_text"] = "\n".join(future_text).strip()

    if ai_strategy:
        result["nature_change_text"] = ai_strategy
    else:
        result["nature_change_text"] = (
            "Rather than making a large decision immediately, it is better to define a small practical step first, "
            "observe the response, and then adjust the direction. "
            "The goal is not forced behavior change, but gradual adjustment of the current nature-flow."
        )

    result["common_comment_text"] = (
        "This result is a reference analysis based on the selected essence, current nature, present state, and past experience patterns. "
        "The important point is not whether the result is absolutely right or wrong, but how root elements and conditions generate a future flow."
    )

    cleanup_keys = [
        "one_line_summary",
        "current_status_text",
        "core_problem_text",
        "future_flow_text",
        "nature_change_text",
        "common_comment_text",
    ]

    for key in cleanup_keys:
        if key in result:
            result[key] = polish_english_text(safe_text(result.get(key)))

    return result


def polish_english_text(text: str) -> str:
    """
    Final English phrase polishing for AI-generated and rule-generated text.
    This is intentionally conservative so that it does not distort meaning.
    """
    replacements = {
        "behavior connection": "practical alignment",
        "behavioral connection": "practical alignment",
        "action connection": "practical alignment",
        "attempt of behavior connection": "gradual nature-flow adjustment",
        "activation": "how the strength comes alive",
        "manifestation": "expression",
        "threat flow": "threat tendency",
        "improvement flow": "improvement tendency",
        "maintenance flow": "maintenance tendency",
        "strengthen the threat tendency": "make the threat tendency stronger",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "  " in text:
        text = text.replace("  ", " ")

    return text.strip()


# =========================================================
# 8. RA 문장 재생성
# =========================================================
def build_ra_narrative(integrated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    RAIS Human Core V3 스타일의 최종 문장 생성.
    index.html이 기존 result 키를 그대로 사용할 수 있도록 필드명 유지.
    """
    if safe_text(integrated_data.get("output_language")).lower().startswith("en"):
        return build_ra_narrative_en(integrated_data)

    result = dict(integrated_data)

    name = result.get("name", "사용자")
    root_state = result.get("root_state", {}) or {}
    root_score = clamp(result.get("root_score", avg([
        root_state.get("stability", 50),
        root_state.get("drive", 50),
        root_state.get("cognition", 50),
        root_state.get("relation", 50),
    ])))

    path_decision = result.get("path_decision", {})
    final_decision = ""
    if isinstance(path_decision, dict):
        final_decision = safe_text(path_decision.get("final_decision"))
    else:
        final_decision = safe_text(path_decision)

    overall_label = score_to_label(root_score)

    ai_core = safe_text(result.get("ai_core_problem"))
    ai_future = safe_text(result.get("ai_future_prediction"))
    ai_strategy = safe_text(result.get("ai_strategy"))
    ai_exp = safe_text(result.get("ai_experience_interpretation"))
    ai_note = safe_text(result.get("ai_adjustment_note"))
    ai_review = result.get("ai_judgement_review", {})
    if not isinstance(ai_review, dict):
        ai_review = {}

    missing = safe_text(ai_review.get("missing_points"))
    disagreement = safe_text(ai_review.get("disagreement"))

    # 0. 한 줄 요약
    if result.get("ai_used"):
        decision_part = f" 최종 흐름은 '{final_decision}' 중심입니다." if final_decision else ""
        result["one_line_summary"] = (
            f"현재는 '{overall_label}' 수준으로, RAIS 종합 판단으로 보면, "
            f"현재 강점보다 실행 조건과 반복 부담을 먼저 조절해야 하는 흐름입니다.{decision_part}"
        )
    else:
        result["one_line_summary"] = result.get("one_line_summary") or (
            f"현재는 '{overall_label}' 수준으로, 선택에 따라 흐름이 달라질 수 있습니다."
        )

    # 1. 현재 상태는 v1 문장을 기본 유지
    base_current = safe_text(result.get("current_status_text"))
    if not base_current:
        base_current = f"{name}님의 현재 상태는 전반적으로 {overall_label} 수준입니다."
    result["current_status_text"] = base_current

    # 2. 핵심 문제: AI를 앞에 두되 RAIS 보정 문장으로 고정
    if ai_core:
        extra = []
        if missing:
            extra.append("추가로 보완하면, 과거 경험 점수가 모두 50으로 중립적이지만, "
                         "이 부분이 미래 흐름에서 위협 요소를 다소 완화하는 역할을 한다는 점입니다. "
                         "또한, 환경 기반이 부족하여 실행 조건이 매우 제한적임을 참고할 필요가 있습니다.")
        if disagreement:
            extra.append(f"다만 v1 판단과 다르게 볼 수 있는 부분은 '{disagreement}'입니다.")
        result["core_problem_text"] = (
            f"{ai_core}\n\n"
            "RAIS 분석 관점에서는 이 문제가 단순한 약점이 아니라, "
            "본질이 현재 본성과 현실 조건을 통해 실제 행동으로 충분히 연결되지 못하는 지점으로 해석됩니다."
            + ("\n" + "\n".join(extra) if extra else "")
        )
    elif not safe_text(result.get("core_problem_text")):
        result["core_problem_text"] = build_core_problem_from_vectors(result)

    # 3. 미래 흐름: RAIS + AI 보조 통합 서술
    path_dist = result.get("path_distribution", {})
    try:
        if isinstance(path_dist, str):
            path_dist = json.loads(path_dist)
    except Exception:
        path_dist = {}

    improve = round(float(path_dist.get("개선 흐름", 0)), 1)
    maintain = round(float(path_dist.get("유지 흐름", 0)), 1)
    risk = round(float(path_dist.get("위협 흐름", 0)), 1)

    final_decision = ""
    pd = result.get("path_decision", {})
    if isinstance(pd, dict):
        final_decision = safe_text(pd.get("final_decision"))
    else:
        final_decision = safe_text(pd)

    future_text = []

    future_text.append(
        f"최종 판정은 [{final_decision}]입니다. "
        "현재는 개선·유지·위협 요소가 동시에 존재하는 상태이나, "
        "위협 흐름 비중이 비교적 높게 나타납니다. "
        "이는 본성의 변화에 따라 상태는 변할 수 있음을 상기할 필요가 있습니다."
    )

    future_text.append(
        "특히, 실행력 분산과 환경 조건 부족이 결합되면서 "
        "위협 흐름이 더 크게 부각되는 편입니다."
    )

    flows = [
        ("위협 흐름", risk),
        ("유지 흐름", maintain),
        ("개선 흐름", improve),
    ]
    flows_sorted = sorted(flows, key=lambda x: x[1], reverse=True)

    if len(flows_sorted) >= 1:
        future_text.append(
            f"1순위 흐름은 {flows_sorted[0][0]}({flows_sorted[0][1]}%)이며, "
            "현재 가장 우선적으로 고려해야 할 방향입니다."
        )

    if len(flows_sorted) >= 2:
        future_text.append(
            f"2순위 흐름은 {flows_sorted[1][0]}({flows_sorted[1][1]}%)이며, "
            "보조적으로 함께 영향을 미칩니다."
        )

    if len(flows_sorted) >= 3:
        future_text.append(
            f"보조 흐름 참고 – {flows_sorted[2][0]}({flows_sorted[2][1]}%): "
            "상황과 본성 선택에 따라 분석 결과에 일부 영향을 줄 수 있습니다."
        )

    if ai_future:
        future_text.append(ai_future)

    elif ai_exp:
        future_text.append(
            "과거 경험이 중간 수준으로 안정적이지만, 특별한 강점이나 회복력은 부족하여 "
            "위협 흐름이 우선적으로 작용할 가능성이 큽니다. "
            "유지 흐름이 그 다음이며, 개선 흐름은 보조적입니다. "
            "현재 건강과 사고 판단 자원은 비교적 살아 있어 개선 가능성은 있으나, "
            "환경과 경험 기반이 낮아 실행에 제약이 있습니다. "
            "또한, 과거 경험은 성공과 실패 회복, 신뢰, 일관성 모두 중간 수준으로 안정적이나, "
            "특히 강한 회복력이나 신뢰 기반은 보강이 필요합니다. "
            "이로 인해 향후 흐름에서는 위협 요소가 삶의 방향을 고착화할 위험이 있습니다. "
            "본성 변화와 환경 조건에 따라 흐름이 크게 개선될 수 있으므로 "
            "위협 요소를 줄여가는 방향을 모색해야 할 것입니다."
        )

    result["future_flow_text"] = "\n".join(future_text).strip()

    # 4. 행동 조정 방향
    if ai_strategy:
        result["nature_change_text"] = ai_strategy
    elif not safe_text(result.get("nature_change_text")):
        result["nature_change_text"] = build_default_action_direction(result)

    # 공통 설명
    result["common_comment_text"] = (
        "이 결과는 입력된 본질·본성·현재 상태·과거 경험 패턴을 바탕으로 "
        "현재 흐름과 미래 방향을 해석한 참고 자료입니다. "
        "최종 출력은 RAIS 구조에 맞게 정리한 결과입니다. "
        "중요한 것은 결과의 맞고 틀림보다, 근본 요소의 선택과 조건에 따라 어떤 흐름이 생성되는지 이해하는 것입니다."
    )

    cleanup_keys = [
        "one_line_summary",
        "current_status_text",
        "core_problem_text",
        "future_flow_text",
        "nature_change_text",
        "common_comment_text",
    ]

    for key in cleanup_keys:
        if key in result:
            text = safe_text(result.get(key))
            text = text.replace("AI 검토에서는", "")
            text = text.replace("AI 검토 결과", "추가 분석 결과")
            text = text.replace("AI 검토 기반", "종합 분석 기반")
            #text = text.replace("AI", "")
            text = text.replace("RAIS-AI", "RAIS")
            text = soften_sentence(text)
            result[key] = text.strip()

    return result

def build_core_problem_from_vectors(result: Dict[str, Any]) -> str:
    threats = normalize_vector_list(result.get("threat_vectors", []), "위협 요인")
    if threats:
        top = threats[0]
        return f"현재 가장 먼저 살펴볼 부분은 '{top['factor']}'입니다. {top.get('rationale', '')}"
    return "현재 핵심 문제는 하나로 단정하기보다, 본질과 본성이 실제 행동으로 연결되는 정도를 점검하는 데 있습니다."


def build_default_action_direction(result: Dict[str, Any]) -> str:
    threats = normalize_vector_list(result.get("threat_vectors", []), "위협 요인")
    opps = normalize_vector_list(result.get("opportunity_vectors", []), "기회 요인")

    lines = []
    if threats:
        lines.append(f"먼저 '{threats[0]['factor']}' 부담을 줄이는 방향이 필요합니다.")
    if opps:
        lines.append(f"동시에 '{opps[0]['factor']}' 자원을 활용하면 진로 방향을 안정시키는 데 도움이 됩니다.")

    lines.append("큰 결정보다 작은 실행을 먼저 정하고, 실행 후 반응을 보며 방향을 조정하는 방식이 적절합니다.")
    return "\n".join(lines)

def soften_sentence(text: str) -> str:
    replacements = {
        "반드시 필요합니다": "필요할 수 있습니다",
        "문제입니다": "점검할 지점입니다",
        "부족합니다": "보완되어야 할 여지가 있습니다",
        "위험합니다": "주의가 필요한 흐름입니다",
        "실패할 수 있습니다": "어려움이 커질 수 있습니다",
        "해야 합니다": "하는 것이 좋습니다",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

# =========================================================
# 9. 메인 엔진: app.py가 호출하는 함수
# =========================================================
def build_ra_result(raw_input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    app.py는 기존처럼 build_ra_result(input_data)만 호출하면 됨.

    흐름:
    입력
    → v1 RA 결과 생성
    → RA 구조 생성
    → AI 분석 요청
    → AI 결과 수집
    → AI 결과 분해
    → RA 구조 매핑
    → RAIS 보정/통합
    → 최종 결과 출력
    """

    output_language = detect_output_language(raw_input_data)
    data = normalize_input_data(raw_input_data)
    data["lang"] = output_language
    data["output_language"] = output_language

    # 1. 기존 v1 결과 생성
    try:
        base_result = v1.build_ra_result(data)
    except Exception:
        # print("RAIS V3 base v1 build_ra_result error:")
        traceback.print_exc()
        base_result = build_fallback_result(data)

    if not isinstance(base_result, dict) or not base_result:
        base_result = build_fallback_result(data)

    # 2. RA 구조 생성
    ra_structure = build_ra_structure(data, base_result)

    # 3. AI prompt 생성
    prompt = build_ai_prompt(ra_structure, output_language=output_language)

    # 4. AI 분석 요청
    ai_result = call_ai_analysis(prompt)
    ai_text = ai_result.get("raw_text", "") if isinstance(ai_result, dict) else str(ai_result or "")

    # 5. AI 응답 분해
    parsed = parse_ai_result(ai_text)

    # 6. RA 구조 매핑
    mapped = map_to_ra_structure(parsed, ra_structure)

    # 7. RAIS 보정/통합
    integrated = integrate_ai_results(mapped, ra_structure, base_result)
    integrated["output_language"] = output_language

    # 8. 최종 문장 생성
    result = build_ra_narrative(integrated)

    if not isinstance(result, dict) or not result:
        result = base_result

    # 9. 그래프/템플릿 안전장치
    result.setdefault("root_state", base_result.get("root_state", {
        "stability": 50.0,
        "health": 50.0,
        "execution": 50.0,
        "hw_score": 50.0,
        "sw_score": 50.0,
        "root_score": 50.0,
    }))
    if not isinstance(result.get("root_state"), dict):
        result["root_state"] = {}

    result["root_state"].setdefault("stability", result.get("root_score", 50.0) or 50.0)
    result["root_state"].setdefault("health", result.get("hw_score", 50.0) or 50.0)
    result["root_state"].setdefault("execution", result.get("sw_score", 50.0) or 50.0)

    result.setdefault("path_distribution", base_result.get("path_distribution", {
        "개선 경로": 0.0,
        "완만 개선": 0.0,
        "유지 경로": 100.0,
        "완만 위협": 0.0,
        "위협 경로": 0.0,
    }))

    result.setdefault("threat_vectors", base_result.get("threat_vectors", []))
    result.setdefault("opportunity_vectors", base_result.get("opportunity_vectors", []))

    # 10. 디버그/검증용 내부 데이터
    result["ai_prompt_preview"] = prompt[:2000]
    result["ai_raw_text"] = ai_text[:4000] if ai_text else ""
    result["ra_structure_v3"] = ra_structure
    result["engine"] = MODEL_VERSION
    result["output_language"] = output_language

    return result


# =========================================================
# 10. 로컬 단독 테스트
# =========================================================
if __name__ == "__main__":
    """
    sample = {
        "name": "테스트",
        "gender": "남성",
        "age": "55",
        "current_job": "자영업/사업",
        "essences": ["학습성", "추진성", "안전성"],
        "natures": ["분석형", "전략형", "주도성", "신중형"],
        "current_status": {"건강": 60, "실행": 55},
        "execution": {"환경": 50, "경제 여건": 45},
        "experience": {
            "success": 65,
            "failure_recovery": 55,
            "items": [
                {"분야": "사업", "성과": "성공", "주된 이유": "역량 적합"},
                {"분야": "조직", "성과": "보통", "주된 이유": "관계 문제"},
            ],
        },
    }

    output = build_ra_result(sample)
    print(json.dumps({
        "engine": output.get("engine"),
        "one_line_summary": output.get("one_line_summary"),
        "current_status_text": output.get("current_status_text"),
        "core_problem_text": output.get("core_problem_text"),
        "future_flow_text": output.get("future_flow_text"),
        "nature_change_text": output.get("nature_change_text"),
        "ai_used": output.get("ai_used"),
    }, ensure_ascii=False, indent=2))
    """
