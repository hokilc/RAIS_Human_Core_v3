from __future__ import annotations

from typing import Any
from flask import Flask, render_template, request
import os
#  print(os.getenv("OPENAI_API_KEY"))
import sys
from pprint import pformat
from datetime import date, datetime
import traceback
from rais_engine.rais_human_core_v3 import (
    normalize_input_data,
    build_ra_result,
    post_process_result,
    build_fallback_result,
)
import json
import requests


#    url = "https://script.google.com/macros/s/AKfycby3ykbSOlxszCQuPQqyFs-kH1-NfHtJMiZywq-4PUoJZkVV887hN0u3Pjv30iWXwBaSmQ/exec"

def send_to_google_sheets(result):
    url = "https://script.google.com/macros/s/AKfycby_aHbfQbveeeqZmhZY2p9hRopX5d8snKRzxTnoxzGptPIUOee6n7H4KkgRRcKhCGZQHA/exec"

    payload = {
        "secret": "RAIS_SECRET_1234",
        "timestamp": datetime.now().isoformat(),

        "name": result.get("name", ""),
        "root_score": result.get("root_score", ""),
        "hw_score": result.get("hw_score", ""),
        "sw_score": result.get("sw_score", ""),
        "path_decision": result.get("path_decision", ""),
        "one_line_summary": result.get("one_line_summary", ""),
        "engine": result.get("engine", ""),
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        # print("Google Sheets response:", r.status_code, r.text)
    except Exception as e:
        print("Google Sheets send error:", e)

def save_log(input_data, result):
    try:
        log_data = {
            "timestamp": datetime.now().isoformat(),

            # 🔥 수정 핵심
            "essence_selected": ", ".join(input_data.get("essences", [])),
            "nature_selected": ", ".join(input_data.get("natures", [])),

            "root_score": result.get("root_score"),
            "hw_score": result.get("hw_score"),
            "sw_score": result.get("sw_score"),

            # 🔥 이것도 수정 필요
            "path_decision": result.get("path_decision"),

            # 🔥 dict → 문자열 변환
            "path_distribution": json.dumps(result.get("path_distribution", {})),

            "one_line_summary": result.get("one_line_summary"),
            "engine": result.get("engine"),
        }

        # ① 콘솔 출력 (즉시 확인)
        # print("\n🔥 RAIS LOG DATA:")
        # print(log_data)

        # ② 파일 저장
        with open("rais_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + "\n")

    except Exception as e:
        print("LOG ERROR:", e)

#print("RA_MODEL MODULE FILE:", ra_model_v2.__file__)
#app = Flask(__name__)

# =========================================================
# 0. PyInstaller 대응 (핵심)
# =========================================================
def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)


# =========================================================
# 다국어 텍스트
# =========================================================
LANG_TEXT = {
    "ko": {
        "app_title": "근본 분석 지능 시스템 v3",
        "language_label": "언어 선택",
        "analyze_button": "분석 실행",
        "guide_button": "사용 방법 보기",
        "brand": "근본 분석 지능 시스템",
        "subtitle": "현재를 진단하고, 구조를 해석하며, 미래 방향을 예측하는 근본 분석 지능 시스템",
        "notice": "이 분석은 ‘정답’을 맞추는 것이 아니라, 현재의 ‘흐름’을 분석하는 도구입니다.",
        "feature_1": "현재 상태 진단",
        "feature_2": "구조적 영향 흐름 분석",
        "feature_3": "미래 방향 예측",
        "start_button": "분석 시작하기",
        "disclaimer": "※ 본 시스템은 채용·승진·인사 평가 등의 절대적 판단 기준으로 사용하는 것을 권장하지 않습니다.",
        "guide_title": "사용 방법 안내",

        "guide_step1_title": "1. 기본 정보 입력",
        "guide_step1_text": "간단한 사용자 정보를 입력합니다. 이름은 가명으로 입력해도 됩니다.(권장)",

        "guide_step2_title": "2. 본질 / 본성 선택",
        "guide_step2_text1": "본질은 부모로부터 물려받은 성향 또는 어릴적부터 비교적 변하지 않았던 성격을 말합니다.",
        "guide_step2_text2": "선택 우선순위가 분석에 반영됩니다. 가장 잘 맞는 항목부터 순서대로 3가지 선택하세요.",
        "guide_step2_text3": "본성은 현재 나의 성격과 행동 흐름을 말합니다. 주성향과 보조 성향으로 나누어 2가지를 선택하세요.",
        "guide_step2_text4": "(A~G) 7가지 항목을 순서대로 선택하세요.",

        "guide_step3_title": "3. 현재 나의 상태 선택",
        "guide_step3_text": "현재 나의 목표 / 고민 / 준비 상태 / 건강 상태를 선택합니다.",

        "guide_step4_title": "4. 과거 경험 패턴 선택",
        "guide_step4_text1": "과거 경험은 최대 3가지까지 입력 가능합니다.",
        "guide_step4_text2": "직업 / 분야 / 결과 / 이유를 선택합니다.",
        "guide_step4_text3": "[경험 추가] 버튼으로 추가 입력 가능합니다.",

        "guide_step5_title": "5. 실행",
        "guide_step5_text1": "입력이 완료되면 [근본 분석 실행] 버튼을 누르세요.",
        "guide_step5_text2": "잠시 후 분석 결과를 확인할 수 있습니다.",

        "guide_result_title": "결과 출력과 입력 초기화",
        "guide_result_text1": "[출력] 버튼으로 결과를 인쇄할 수 있습니다.",
        "guide_result_text2": "[입력 초기화] 버튼으로 다시 시작할 수 있습니다.",

        "back_home": "처음으로",
        "analyze_title": "근본 분석 실행",
        "section_basic": "기본 정보",
        "section_essence": "본질 선택",
        "section_nature": "본성 선택",
        "section_current": "현재 상태",
        "section_experience": "과거 경험",
        "run_analysis": "근본 분석 실행",
        "reset_input": "입력 초기화",
        "result_title": "분석 결과",

        "section_execute": "5. 실행",
        "add_experience": "경험 추가",

        "label_name": "이름",
        "label_gender": "성별",
        "label_birth": "출생연월",
        "label_job": "현재 직업",

        "label_essence_1": "본질 1순위",
        "label_essence_2": "본질 2순위",
        "label_essence_3": "본질 3순위",
        "label_primary": "주 성향",
        "label_secondary": "보조 성향",
        "top_message": "현재를 진단하고, 미래 방향을 예측합니다",
        "sub_message": "왜 막히는지, 어디로 가야 하는지 알려드립니다. 아래 항목을 입력하고 근본 분석을 실행하세요.",
        "desc_current_state": "삶의 방향, 현실 조건, 건강 기반을 함께 봅니다.",
        "desc_past_experience": "과거 경험에서 어떤 분야가 잘 맞았고, 어떤 이유로 어려움이 있었는지 간단히 선택합니다.",
        "desc_execute": "입력 내용을 바탕으로 근본 분석을 실행합니다.",
        "label_current_goal": "현재 목표",
        "label_current_concern": "현재 고민",
        "label_environment": "협력/자원/환경/준비",
        "label_health": "신체/건강 상태",
        "option_select": "선택",
        "delete_button": "삭제",
        "label_result": "결과",
        "label_field": "분야",
        "label_past_job": "과거 직업",
        "option_year": "연도",
        "option_month": "월",
        "desc_essence_nature": "본질은 3개 이내, 본성은 A~G 각 그룹에서 주/보조 2개 이내로 선택합니다.",
        "label_essence_select": "본질 선택",
        "label_nature_select": "본성 선택",
        "label_main_reason": "주된 이유",
        "label_experience_1": "경험",
        "nature_group_a": "A. 행동/추진",
        "nature_group_b": "B. 인지/사고",
        "nature_group_c": "C. 관계/사회",
        "nature_group_d": "D. 안정/변화",
        "nature_group_e": "E. 내부 상태",
        "nature_group_f": "F. 판단/결정",
        "nature_group_g": "G. 활동성/활력",
        "essence_adaptability": "적응성 : 환경 변화에 맞추어 상태를 조정하고 확장하는 힘",
        "essence_learning": "학습성 : 인지, 기억, 이해, 판단을 통해 상황을 발전시키는 힘",
        "essence_relation": "관계성 : 타인, 집단, 대상과 연결하고 조정하는 힘",
        "essence_expression": "표현성 : 내부 상태와 생각을 외부로 드러내고 발신하는 힘",
        "essence_drive": "추진성 : 목표를 향해 행동하고 밀고 나가는 힘",
        "essence_safety": "안전성 : 상태를 유지하고 안정시키며 손상을 줄이려는 힘",
        "essence_reaction": "반응성 : 자극, 변화, 위험, 감정 신호를 빠르게 감지하는 힘",
        "essence_masculinity": "남성성 : 구조, 추진, 집중, 경쟁 흐름과 연결되는 성향",
        "essence_femininity": "여성성 : 공감, 관계, 섬세함, 조율 흐름과 연결되는 성향",
        "nature_execution": "실행성",
        "nature_challenge": "도전성",
        "nature_drive": "추진력",
        "nature_initiative": "주도성",
        "nature_responsibility": "책임감",
        "nature_active": "능동성",
        "nature_competitive": "경쟁성",
        "nature_analysis": "분석력",
        "nature_inquiry": "탐구성",
        "nature_judgment": "판단력",
        "nature_creativity": "창의성",
        "nature_logic": "논리성",
        "nature_intuition": "직관력",
        "nature_relation_oriented": "관계지향성",
        "nature_relation_harmony": "관계조화성",
        "nature_influence": "영향력",
        "nature_empathy": "공감성",
        "nature_communication": "소통성",
        "nature_inclusion": "포용성",
        "nature_expression": "표현력",
        "nature_understanding": "이해력",
        "nature_self_expression": "자기표현성",
        "nature_stability": "안정지향성",
        "nature_change": "변화지향성",
        "nature_expansion": "확장성",
        "nature_conservative": "보수성",
        "nature_risk_avoidance": "위험회피성",
        "nature_desire": "욕구강조성",
        "nature_anxiety_sensitive": "불안민감성",
        "nature_self_centered": "자기중심성",
        "nature_emotion_fluctuation": "감정변동성",
        "nature_stress_sensitive": "스트레스민감성",
        "nature_comparison_sensitive": "비교민감성",
        "nature_careful": "신중성",
        "nature_intuition_decision": "직관성",
        "nature_analysis_decision": "분석성",
        "nature_avoidance": "회피성",
        "nature_strategy": "전략성",
        "nature_impulsive": "즉흥성",
        "nature_decision": "결단성",
        "nature_high_energy": "고활력성",
        "nature_persistence": "지속성",
        "nature_low_energy": "저활력성",
        "nature_energy_fluctuation": "활력변동성",
        "nature_concentration": "집중성",
        "nature_fatigue_sensitive": "피로민감성",
        "nature_rhythm_stability": "리듬안정성",

        "exp_job_agriculture": "농축산어업",
        "exp_job_business_owner": "자영업/사업",
        "exp_job_employee": "회사원",
        "exp_job_public": "공무원/공공직",
        "exp_job_education": "교육직",
        "exp_job_professional": "연구/전문직",
        "exp_job_technical": "기능/기술직",
        "exp_job_culture": "문화/예술/체육",
        "exp_job_healthcare": "보건/복지/돌봄",
        "exp_job_service_sales": "서비스/판매",
        "exp_job_homemaker": "가정/전업주부",
        "exp_job_student": "학생",
        "exp_job_freelancer": "프리랜서",
        "exp_job_part_time": "일용직/알바",
        "exp_job_retired_transition": "은퇴/전환기",
        "exp_job_unemployed_other": "무직/기타",

        "exp_field_research": "연구·분석 분야",
        "exp_field_execution": "실행·사업 분야",
        "exp_field_relationship": "관계·중재 분야",
        "exp_field_expression": "표현·창작 분야",
        "exp_field_management": "관리·안정 분야",
        "exp_field_sensing": "감지·직관 분야",

        "exp_result_success": "성공",
        "exp_result_stable": "안정",
        "exp_result_normal": "보통",
        "exp_result_resigned": "사퇴",
        "exp_result_failure": "실패",

        "exp_reason_fit": "역량 적합",
        "exp_reason_relationship": "관계 문제",
        "exp_reason_health": "건강 문제",
        "exp_reason_economic": "경제 여건",
        "exp_reason_execution": "실행 부족",
        "exp_reason_direction": "방향 혼란",
        "exp_reason_external": "외부 환경",

        "goal_family_peace": "가정 평화",
        "goal_health_recovery": "건강 회복",
        "goal_economic_stability": "경제적 안정",
        "goal_performance_jump": "성과 도약",
        "goal_life_margin": "삶의 여유",
        "goal_social_contribution": "사회 기여",
        "goal_social_recognition": "사회적 인정",
        "goal_relationship_improvement": "관계 개선",
        "goal_personality_change": "성격 변화",
        "goal_keep_job": "현 직업 유지",
        "goal_new_job": "새 직업 탐색",
        "goal_no_worry": "고민 없음",

        "state_very_poor": "매우 열악함",
        "state_poor": "열악한 편",
        "state_trying": "노력 중",
        "state_hopeful": "희망적",
        "state_ready": "준비 완료",

        "health_strong": "강건",
        "health_vital": "활력",
        "health_normal": "보통",
        "health_weak": "약함",
        "health_ill": "병중",

        "gender_male": "남성",
        "gender_female": "여성",
    },
    "en": {
        "app_title": "Root Analysis Intelligence System v3",
        "language_label": "Language",
        "analyze_button": "Run Analysis",
        "guide_button": "View Guide",
        "brand": "Root Analysis Intelligence System",
        "subtitle": "A root analysis intelligence system that diagnoses the present, interprets structure, and predicts future direction.",
        "notice": "This analysis is not intended to find a fixed answer, but to interpret the current flow.",
        "feature_1": "Current State Diagnosis",
        "feature_2": "Structural Influence Flow Analysis",
        "feature_3": "Future Direction Prediction",
        "start_button": "Start Analysis",
        "disclaimer": "※ This system is not recommended as an absolute standard for hiring, promotion, or personnel evaluation.",
        "guide_title": "User Guide",

        "guide_step1_title": "1. Basic Information",
        "guide_step1_text": "Enter simple user information. A nickname is recommended.",

        "guide_step2_title": "2. Essence / Nature Selection",
        "guide_step2_text1": "Essence refers to inherited or relatively stable personality traits.",
        "guide_step2_text2": "Selection priority affects analysis results. Choose up to 3 in order.",
        "guide_step2_text3": "Nature represents current personality and behavioral flow.",
        "guide_step2_text4": "Select items from categories A to G.",

        "guide_step3_title": "3. Current State Selection",
        "guide_step3_text": "Select your goals, concerns, preparation status, and health state.",

        "guide_step4_title": "4. Past Experience Patterns",
        "guide_step4_text1": "You may enter up to 3 past experiences.",
        "guide_step4_text2": "Select job, field, result, and main reason.",
        "guide_step4_text3": "Use [Add Experience] to enter more.",

        "guide_step5_title": "5. Run Analysis",
        "guide_step5_text1": "After completing input, click [Run Root Analysis].",
        "guide_step5_text2": "Results will appear shortly after analysis.",

        "guide_result_title": "Print & Reset",
        "guide_result_text1": "Use [Print] to print analysis results.",
        "guide_result_text2": "Use [Reset] to start over.",

        "back_home": "Back Home",
        "analyze_title": "Root Analysis",
        "section_basic": "Basic Information",
        "section_essence": "Essence Selection",
        "section_nature": "Nature Selection",
        "section_current": "Current State",
        "section_experience": "Past Experience",
        "run_analysis": "Run Root Analysis",
        "reset_input": "Reset Input",
        "result_title": "Analysis Result",

        "section_execute": "5. Execute",
        "add_experience": "Add Experience",

        "label_name": "Name",
        "label_gender": "Gender",
        "label_birth": "Year / Month of Birth",
        "label_job": "Current Job",

        "label_essence_1": "Essence Priority 1",
        "label_essence_2": "Essence Priority 2",
        "label_essence_3": "Essence Priority 3",
        "label_primary": "Primary",
        "label_secondary": "Secondary",
        "top_message": "Diagnose the present and predict future direction",
        "sub_message": "This system helps you understand why you are blocked and where to move next. Enter the items below and run the analysis.",
        "desc_current_state": "This section reviews your life direction, real conditions, and health foundation together.",
        "desc_past_experience": "Briefly select which past fields fit you well and why difficulties occurred.",
        "desc_execute": "Run root analysis based on the information entered.",
        "label_current_goal": "Current Goal",
        "label_current_concern": "Current Concern",
        "label_environment": "Cooperation / Resources / Environment / Preparation",
        "label_health": "Physical / Health State",
        "option_select": "Select",
        "delete_button": "Delete",
        "label_result": "Result",
        "label_field": "Field",
        "label_past_job": "Past Job",
        "option_year": "year",
        "option_month": "month",
        "label_main_reason": "Main Reason",
        "desc_essence_nature": "Select up to 3 essence traits, and up to 2 primary/secondary nature traits from each A–G group.",
        "label_essence_select": "Essence Selection",
        "label_nature_select": "Nature Selection",
        "label_experience_1": "Experience",
        "nature_group_a": "A. Action / Drive",
        "nature_group_b": "B. Cognition / Thinking",
        "nature_group_c": "C. Relationship / Social",
        "nature_group_d": "D. Stability / Change",
        "nature_group_e": "E. Inner State",
        "nature_group_f": "F. Judgment / Decision",
        "nature_group_g": "G. Activity / Vitality",
        "essence_adaptability": "Adaptability: Adjusting and expanding in response to change",
        "essence_learning": "Learning: Developing through cognition, memory, understanding, and judgment",
        "essence_relation": "Relationality: Connecting and coordinating with people, groups, and objects",
        "essence_expression": "Expressiveness: Sending thoughts and inner states outward",
        "essence_drive": "Drive: Moving toward goals and taking action",
        "essence_safety": "Safety: Maintaining stability and reducing damage",
        "essence_reaction": "Responsiveness: Quickly sensing change, risk, emotion, and signals",
        "essence_masculinity": "Masculinity: A tendency linked to structure, drive, focus, and competition",
        "essence_femininity": "Femininity: A tendency linked to empathy, relationship, sensitivity, and coordination",
        "nature_execution": "Execution",
        "nature_challenge": "Challenge",
        "nature_drive": "Driving Force",
        "nature_initiative": "Initiative",
        "nature_responsibility": "Responsibility",
        "nature_active": "Proactiveness",
        "nature_competitive": "Competitiveness",
        "nature_analysis": "Analytical Ability",
        "nature_inquiry": "Inquiry",
        "nature_judgment": "Judgment",
        "nature_creativity": "Creativity",
        "nature_logic": "Logic",
        "nature_intuition": "Intuition",
        "nature_relation_oriented": "Relationship Orientation",
        "nature_relation_harmony": "Relationship Harmony",
        "nature_influence": "Influence",
        "nature_empathy": "Empathy",
        "nature_communication": "Communication",
        "nature_inclusion": "Inclusiveness",
        "nature_expression": "Expressiveness",
        "nature_understanding": "Understanding",
        "nature_self_expression": "Self-Expression",
        "nature_stability": "Stability Orientation",
        "nature_change": "Change Orientation",
        "nature_expansion": "Expandability",
        "nature_conservative": "Conservativeness",
        "nature_risk_avoidance": "Risk Avoidance",
        "nature_desire": "Desire-Oriented",
        "nature_anxiety_sensitive": "Anxiety Sensitivity",
        "nature_self_centered": "Self-Centeredness",
        "nature_emotion_fluctuation": "Emotional Fluctuation",
        "nature_stress_sensitive": "Stress Sensitivity",
        "nature_comparison_sensitive": "Comparison Sensitivity",
        "nature_careful": "Carefulness",
        "nature_intuition_decision": "Intuitiveness",
        "nature_analysis_decision": "Analytical Tendency",
        "nature_avoidance": "Avoidance",
        "nature_strategy": "Strategic Thinking",
        "nature_impulsive": "Impulsiveness",
        "nature_decision": "Decisiveness",
        "nature_high_energy": "High Energy",
        "nature_persistence": "Persistence",
        "nature_low_energy": "Low Energy",
        "nature_energy_fluctuation": "Energy Fluctuation",
        "nature_concentration": "Concentration",
        "nature_fatigue_sensitive": "Fatigue Sensitivity",
        "nature_rhythm_stability": "Rhythm Stability",

        "exp_job_agriculture": "Agriculture / Livestock / Fishery",
        "exp_job_business_owner": "Self-employed / Business",
        "exp_job_employee": "Company Employee",
        "exp_job_public": "Public Official / Public Sector",
        "exp_job_education": "Education",
        "exp_job_professional": "Research / Professional",
        "exp_job_technical": "Technical / Skilled Work",
        "exp_job_culture": "Culture / Arts / Sports",
        "exp_job_healthcare": "Healthcare / Welfare / Care",
        "exp_job_service_sales": "Service / Sales",
        "exp_job_homemaker": "Homemaker",
        "exp_job_student": "Student",
        "exp_job_freelancer": "Freelancer",
        "exp_job_part_time": "Day Labor / Part-time",
        "exp_job_retired_transition": "Retired / Transition Period",
        "exp_job_unemployed_other": "Unemployed / Other",

        "exp_field_research": "Research / Analysis Field",
        "exp_field_execution": "Execution / Business Field",
        "exp_field_relationship": "Relationship / Mediation Field",
        "exp_field_expression": "Expression / Creative Field",
        "exp_field_management": "Management / Stability Field",
        "exp_field_sensing": "Sensing / Intuition Field",

        "exp_result_success": "Success",
        "exp_result_stable": "Stable",
        "exp_result_normal": "Normal",
        "exp_result_resigned": "Resigned",
        "exp_result_failure": "Failure",

        "exp_reason_fit": "Capability Fit",
        "exp_reason_relationship": "Relationship Issue",
        "exp_reason_health": "Health Issue",
        "exp_reason_economic": "Economic Conditions",
        "exp_reason_execution": "Lack of Execution",
        "exp_reason_direction": "Direction Confusion",
        "exp_reason_external": "External Environment",

        "goal_family_peace": "Family Peace",
        "goal_health_recovery": "Health Recovery",
        "goal_economic_stability": "Economic Stability",
        "goal_performance_jump": "Performance Growth",
        "goal_life_margin": "More Life Margin",
        "goal_social_contribution": "Social Contribution",
        "goal_social_recognition": "Social Recognition",
        "goal_relationship_improvement": "Relationship Improvement",
        "goal_personality_change": "Personality Change",
        "goal_keep_job": "Maintain Current Job",
        "goal_new_job": "Explore New Job",
        "goal_no_worry": "No Major Concern",

        "state_very_poor": "Very Poor",
        "state_poor": "Poor",
        "state_trying": "Trying",
        "state_hopeful": "Hopeful",
        "state_ready": "Ready",

        "health_strong": "Strong",
        "health_vital": "Vital",
        "health_normal": "Normal",
        "health_weak": "Weak",
        "health_ill": "Ill",

        "gender_male": "Male",
        "gender_female": "Female",
        },
    }


# =========================================================
# 다국어 결과/오류 보조
# =========================================================
def get_lang_from_request(default: str = "ko") -> str:
    """
    GET/POST 양쪽에서 언어값을 안정적으로 읽는다.
    """
    lang = request.form.get("lang") if request.method == "POST" else request.args.get("lang")
    lang = safe_text(lang or default)
    return lang if lang in LANG_TEXT else "ko"


def attach_lang_to_input(input_data: dict, lang: str) -> dict:
    """
    분석 엔진(v1/v3)이 영어 결과 분기를 사용할 수 있도록 lang을 명시적으로 전달한다.
    Flask request.form(ImmutableMultiDict)은 직접 수정할 수 없으므로 raw는 복사해서 보존한다.
    """
    if not isinstance(input_data, dict):
        return input_data

    input_data["lang"] = lang
    input_data["language"] = lang
    input_data["ui_lang"] = lang

    raw = input_data.get("raw")
    if raw is not None:
        try:
            if hasattr(raw, "to_dict"):
                raw_copy = raw.to_dict(flat=False)
            elif isinstance(raw, dict):
                raw_copy = dict(raw)
            else:
                raw_copy = {"_raw": str(raw)}
            raw_copy["lang"] = lang
            input_data["raw"] = raw_copy
        except Exception:
            input_data["raw"] = {"lang": lang}

    return input_data


def ensure_template_safe_result(result: dict, input_data: dict | None = None, lang: str = "ko") -> dict:
    """
    예외 상황에서도 index.html의 그래프/결과 블록이 안전하게 렌더링되도록 기본 필드를 보강한다.
    """
    if not isinstance(result, dict):
        result = {}

    input_data = input_data or {}
    result.setdefault("engine", "RAIS")
    result.setdefault("name", input_data.get("name", ""))

    result.setdefault("root_score", 50.0)
    result.setdefault("hw_score", 50.0)
    result.setdefault("sw_score", 50.0)

    result.setdefault("root_state", {
        "stability": 50.0,
        "health": 50.0,
        "execution": 50.0,
        "cognition": 50.0,
        "relation": 50.0,
        "hw_score": 50.0,
        "sw_score": 50.0,
        "root_score": 50.0,
    })

    if not isinstance(result.get("root_state"), dict):
        result["root_state"] = {
            "stability": 50.0,
            "health": 50.0,
            "execution": 50.0,
            "cognition": 50.0,
            "relation": 50.0,
            "hw_score": 50.0,
            "sw_score": 50.0,
            "root_score": 50.0,
        }

    result.setdefault("path_distribution", {
        "개선 흐름": 33.3,
        "유지 흐름": 33.4,
        "위협 흐름": 33.3,
    })
    result.setdefault("threat_vectors", [])
    result.setdefault("opportunity_vectors", [])

    result.setdefault("talent_analysis_text", "")
    result.setdefault("current_fit_text", "")
    result.setdefault("recommended_jobs_text", "")
    result.setdefault("nature_change_text", "")
    result.setdefault("common_comment_text", "This result is for reference only." if lang == "en" else "이 결과는 참고용입니다.")

    return result



def build_fallback_result_for_lang(input_data: dict, lang: str, error: str | None = None) -> dict:
    """
    오류/예외 상황에서도 언어별 기본 문장을 유지한다.
    """
    name = input_data.get("name", "") if isinstance(input_data, dict) else ""

    if lang == "en":
        if error:
            return {
                "engine": "RAIS",
                "name": name,
                "one_line_summary": "An error occurred during analysis.",
                "current_status_text": f"Error message: {error}",
                "core_problem_text": "There may be an issue in the input processing or engine connection stage.",
                "future_flow_text": "Please check normalize_input_data, build_ra_result, and post_process_result in order.",
                "talent_analysis_text": "",
                "current_fit_text": "",
                "recommended_jobs_text": "",
                "nature_change_text": "",
                "common_comment_text": "This result is for reference only.",
            }

        return {
            "engine": "RAIS",
            "name": name,
            "one_line_summary": "The analysis result could not be generated.",
            "current_status_text": "The input was received, but a problem occurred while generating the result.",
            "core_problem_text": "Please check the input state or the engine calculation process.",
            "future_flow_text": "Please check the connection between normalize_input_data and build_ra_result.",
            "talent_analysis_text": "",
            "current_fit_text": "",
            "recommended_jobs_text": "",
            "nature_change_text": "",
            "common_comment_text": "This result is for reference only.",
        }

    if error:
        return {
            "engine": "RAIS",
            "name": name,
            "one_line_summary": "분석 중 오류가 발생했습니다.",
            "current_status_text": f"오류 메시지: {error}",
            "core_problem_text": "입력 처리 또는 엔진 연결 과정에 오류가 있을 수 있습니다.",
            "future_flow_text": "normalize_input_data / build_ra_result / post_process_result 순서로 점검이 필요합니다.",
            "talent_analysis_text": "",
            "current_fit_text": "",
            "recommended_jobs_text": "",
            "nature_change_text": "",
            "common_comment_text": "이 결과는 참고용입니다.",
        }

    return {
        "engine": "RAIS",
        "name": name,
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



# =========================================================
# 1. Cover Page (첫 화면)
# =========================================================
@app.route("/")
def cover():
    lang = request.args.get("lang", "ko")

    if lang not in LANG_TEXT:
        lang = "ko"

    return render_template(
        "cover.html",
        lang=lang,
        t=LANG_TEXT[lang],
    )


# =========================================================
# 2. 사용 설명서
# =========================================================
@app.route("/guide")
def guide():
    lang = request.args.get("lang", "ko")

    if lang not in LANG_TEXT:
        lang = "ko"

    return render_template(
        "guide.html",
        lang=lang,
        t=LANG_TEXT[lang],
    )

# =========================================================
# 3. 분석 화면
# =========================================================
@app.route("/analyze", methods=["GET", "POST"])
def index():
    # print("DEBUG method:", request.method)
    lang = request.args.get("lang", "ko")

    if request.method == "POST":
        lang = request.form.get("lang", "ko")

    if lang not in LANG_TEXT:
        lang = "ko"

    error = None
    result = None
    raw_form_data = {}

    if request.method == "POST":
        try:
            """
            print("DEBUG POST entered")
            print("DEBUG form keys:", list(request.form.keys()))
            print("DEBUG essence:", request.form.getlist("essence"))
            print("DEBUG nature_action:", request.form.getlist("nature_action"))
            print("DEBUG job:", request.form.get("job"))
            print("DEBUG env:", request.form.get("environment_state"))
            print("DEBUG health:", request.form.get("health_state"))
            """

            # 1. 화면 복원용 원본 정리
            raw_form_data = normalize_raw_form_data(request.form)

            # 2. request.form -> 엔진 입력 구조로 변환
            input_data = normalize_input_data(request.form)
            input_data = attach_lang_to_input(input_data, lang)
            raw_form_data["lang"] = lang

            # print("DEBUG normalized input_data:", input_data)

            # 3. 입력 자체가 거의 없는 경우
            if not has_meaningful_form_input(request.form):
                if lang == "en":
                    error = "No input was provided. Please select or enter at least one item before running the analysis."
                else:
                    error = "입력값이 없습니다. 최소 1개 이상 선택 또는 입력한 뒤 분석을 실행해 주세요."
                return render_template(
                    "index.html",
                    raw_form_data=raw_form_data,
                    result=None,
                    error_message=error,
                    lang=lang,
                    t=LANG_TEXT[lang],
                )

            # 4. 필수 입력 검증
            is_valid, missing = has_minimum_required_inputs(input_data)
            if not is_valid:
                if lang == "en":
                    missing_en = {
                        "이름": "Name",
                        "성별": "Gender",
                        "현재 직업": "Current Job",
                        "본질": "Essence",
                        "본성": "Nature",
                    }
                    error = "Please check the following items: " + ", ".join(missing_en.get(x, x) for x in missing)
                else:
                    error = "다음 항목을 확인해 주세요: " + ", ".join(missing)
                return render_template(
                    "index.html",
                    raw_form_data=raw_form_data,
                    result=None,
                    error_message=error,
                    lang=lang,
                    t=LANG_TEXT[lang],
                )

            # 5. 분석 실행
            result = build_ra_result(input_data)
            # print("DEBUG build_ra_result done")

            # 6. fallback
            if not isinstance(result, dict) or not result:
                result = build_fallback_result_for_lang(input_data, lang)

            result = post_process_result(input_data, result)
            result = ensure_template_safe_result(result, input_data, lang)

            save_log(input_data, result)
            send_to_google_sheets(result)

            return render_template(
                "index.html",
                raw_form_data=raw_form_data,
                result=result,
                error_message=None,
                lang=lang,
                t=LANG_TEXT[lang],
            )

        except Exception as e:
            error = str(e)
            traceback.print_exc()

            try:
                raw_form_data = normalize_raw_form_data(request.form)
                input_data = normalize_input_data(request.form)
                input_data = attach_lang_to_input(input_data, lang)
                raw_form_data["lang"] = lang
                result = build_fallback_result_for_lang(input_data, lang, error)
                result = post_process_result(input_data, result)
                result = ensure_template_safe_result(result, input_data, lang)
            except Exception:
                traceback.print_exc()
                result = build_fallback_result_for_lang({}, lang, error)
                if lang == "ko":
                    result["supplemental_path_text"] = "예외 처리 중 추가 오류가 발생했습니다."
                    result["recommendation_text"] = "입력 상태와 엔진 연결 상태를 다시 확인해 주세요."
                else:
                    result["supplemental_path_text"] = "An additional error occurred during exception handling."
                    result["recommendation_text"] = "Please check the input state and engine connection."

            result = ensure_template_safe_result(result, input_data if 'input_data' in locals() else {}, lang)

            return render_template(
                "index.html",
                raw_form_data=raw_form_data,
                result=result,
                error_message=error,
                lang=lang,
                t=LANG_TEXT[lang],
            )

    return render_template(
        "index.html",
        raw_form_data=raw_form_data,
        result=result,
        error_message=error,
        lang=lang,
        t=LANG_TEXT[lang],
    )

# =========================================================
# 1. 공통 유틸
# =========================================================
def nz(value, default=""):
    return default if value is None else str(value).strip()


def pick_first_nonempty(*values, default=""):
    for v in values:
        if v is None:
            continue
        text = str(v).strip()
        if text:
            return text
    return default


def pct_text(value):
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return ""


def label_status_by_score(score):
    try:
        s = float(score)
    except Exception:
        return "판단 보류"

    if s >= 80:
        return "안정"
    elif s >= 65:
        return "다소 안정"
    elif s >= 50:
        return "경계적 균형"
    elif s >= 35:
        return "불안정"
    else:
        return "위험"


def choose_primary_path(improve, maintain, decline):
    vals = {
        "improve": float(improve or 0),
        "maintain": float(maintain or 0),
        "decline": float(decline or 0),
    }
    return max(vals, key=vals.get), vals


def choose_secondary_path(primary_key, vals):
    candidates = [(k, v) for k, v in vals.items() if k != primary_key]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][1]


def path_label_user(path_key):
    mapping = {
        "improve": "완만한 개선",
        "maintain": "유지",
        "decline": "완만한 악화",
    }
    return mapping.get(path_key, "판단 보류")


def normalize_problem_label(problem_text):
    text = nz(problem_text)
    if not text:
        return "핵심 부담 영역"
    return text

def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_list(values) -> list[str]:
    if not values:
        return []
    return [safe_text(v) for v in values if safe_text(v)]


def normalize_raw_form_data(form) -> dict:
    """
    템플릿 재표시용 정규화
    - 단일 값은 문자열
    - 복수 값은 list
    """
    normalized = {}
    for key in form.keys():
        values = form.getlist(key)
        clean_values = [safe_text(v) for v in values if safe_text(v) != ""]
        if not clean_values:
            normalized[key] = ""
        elif len(clean_values) == 1:
            normalized[key] = clean_values[0]
        else:
            normalized[key] = clean_values
    return normalized


def calc_age_from_birth_month(birth_str: str) -> int | None:
    birth_str = safe_text(birth_str)
    if not birth_str:
        return None

    try:
        birth = datetime.strptime(birth_str, "%Y-%m").date()
        today = date.today()

        age = today.year - birth.year
        if today.month < birth.month:
            age -= 1

        if age < 0:
            return None
        return age
    except ValueError:
        return None


def infer_life_stage(age: int | None) -> str:
    if age is None:
        return ""
    if age < 10:
        return "아동기"
    if age < 20:
        return "청소년기"
    if age < 40:
        return "청년기"
    if age < 65:
        return "중년기"
    return "노년기"

def add_josa_ga(text: str) -> str:
    text = safe_text(text)
    if not text:
        return text

    last_char = text[-1]
    code = ord(last_char)

    # 한글이 아닌 경우 기본적으로 "가" 처리
    if not (0xAC00 <= code <= 0xD7A3):
        return text + "가"

    has_batchim = (code - 0xAC00) % 28 != 0
    return text + ("이" if has_batchim else "가")

# =========================================================
# 2. 점수 매핑
# =========================================================
BODY_ESSENCE_SCORE = {
    "건강 강건형": 86,
    "보통 안정형": 72,
    "예민 취약형": 48,
    "활동 지속형": 79,
}

BODY_STATE_SCORE = {
    "건강": 84,
    "보통": 66,
    "약함": 44,
}

BRAIN_ESSENCE_SCORE = {
    "분석·판단형": 82,
    "창의·발상형": 78,
    "실행·조정형": 76,
    "관계·소통형": 74,
}

COG_STATE_SCORE = {
    "좋음": 84,
    "보통": 66,
    "저하": 45,
}

JOB_STATE_SCORE = {
    "현재 직업 유지": 72,
    "전환 준비 중": 64,
    "새 직업 탐색 중": 58,
    "무직/휴직": 42,
}

READINESS_SCORE = {
    "계획 단계": 46,
    "자료 점검": 54,
    "자금 확보": 62,
    "인력 확보": 64,
    "홍보/확산": 60,
    "준비 완료": 84,
}

SUPPORT_SCORE = {
    "매우 부족": 30,
    "부족": 44,
    "보통": 60,
    "양호": 76,
    "매우 양호": 88,
}

ENVIRONMENT_SCORE = {
    "매우 불리": 28,
    "불리": 42,
    "보통": 60,
    "유리": 76,
    "매우 유리": 88,
}

NATURE_BASE_SCORE = {
    "실행성": 78,
    "도전성": 76,
    "추진성": 78,
    "주도성": 76,
    "책임감": 74,
    "능동성": 74,
    "경쟁성": 70,
    "분석형": 80,
    "탐구형": 82,
    "판단형": 79,
    "창의형": 78,
    "관계지향": 76,
    "관계융화": 78,
    "영향력": 76,
    "안정지향": 75,
    "변화지향": 77,
    "확장형": 76,
    "욕구강조": 60,
    "긴장성": 52,
    "자기중심": 56,
    "감정 변동성": 50,
    "신중형": 77,
    "직관형": 72,
    "회피형": 44,
    "전략형": 80,
    "고활력형": 80,
    "지속형": 78,
    "저활력형": 46,
    "변동형": 54,
}


def map_body_score(body_essence_label: str, body_state_label: str) -> float:
    essence_score = BODY_ESSENCE_SCORE.get(safe_text(body_essence_label), 60)
    state_score = BODY_STATE_SCORE.get(safe_text(body_state_label), 60)
    return round((essence_score * 0.55) + (state_score * 0.45), 2)


def map_brain_score(brain_essence_label: str, cog_state_label: str) -> float:
    essence_score = BRAIN_ESSENCE_SCORE.get(safe_text(brain_essence_label), 70)
    state_score = COG_STATE_SCORE.get(safe_text(cog_state_label), 60)
    return round((essence_score * 0.52) + (state_score * 0.48), 2)


def parse_core_essences(values) -> list[str]:
    """
    hidden input pastNature:
    예: '1순위|적응성'
    """
    result = []
    for item in values:
        text = safe_text(item)
        if not text:
            continue
        if "|" in text:
            parts = text.split("|", 1)
            essence = safe_text(parts[1])
        else:
            essence = text
        if essence and essence not in result:
            result.append(essence)
    return result


def parse_current_natures(values) -> list[str]:
    """
    hidden input currentNature:
    예: 'A|주|실행성'
    """
    result = []
    for item in values:
        text = safe_text(item)
        if not text:
            continue
        parts = text.split("|")
        if len(parts) == 3:
            nature_name = safe_text(parts[2])
        else:
            nature_name = text
        if nature_name and nature_name not in result:
            result.append(nature_name)
    return result


def build_nature_items(values) -> list[dict]:
    """
    currentNature 원문을 이용해 주/보조 강도를 다르게 반영
    A|주|실행성
    A|보조|도전성
    """
    items = []
    seen = set()

    for item in values:
        text = safe_text(item)
        if not text:
            continue

        parts = text.split("|")
        if len(parts) == 3:
            _, level, name = parts
            name = safe_text(name)
            level = safe_text(level)
        else:
            name = text
            level = "주"

        if not name or name in seen:
            continue

        base = NATURE_BASE_SCORE.get(name, 72)
        score = max(0, base - 6) if level == "보조" else base

        items.append({
            "name": name,
            "strength_label": level,
            "strength_score": score,
        })
        seen.add(name)

    return items


# =========================================================
# 3. 경험 패턴
# =========================================================
def get_experiences_from_form(form) -> list[dict]:
    """
    name이 아래처럼 있어야 서버에 들어옵니다.
    - exp_field
    - exp_result
    - exp_note
    """
    experiences = []

    fields = form.getlist("exp_field")
    results = form.getlist("exp_result")
    notes = form.getlist("exp_note")

    if fields or results or notes:
        max_len = max(len(fields), len(results), len(notes))
        for i in range(max_len):
            item = {
                "분야": safe_text(fields[i]) if i < len(fields) else "",
                "성과": safe_text(results[i]) if i < len(results) else "",
                "메모": safe_text(notes[i]) if i < len(notes) else "",
            }
            if item["분야"] or item["성과"] or item["메모"]:
                experiences.append(item)
        return experiences

    for idx in range(1, 4):
        field = safe_text(form.get(f"exp_field_{idx}"))
        result = safe_text(form.get(f"exp_result_{idx}"))
        note = safe_text(form.get(f"exp_note_{idx}"))
        if field or result or note:
            experiences.append({
                "분야": field,
                "성과": result,
                "메모": note,
            })

    return experiences


# =========================================================
# 4. 입력 구조화
# =========================================================
def build_input_data(form) -> dict:
    birth = safe_text(form.get("birth"))
    age = calc_age_from_birth_month(birth)
    life_stage = infer_life_stage(age)

    body_essence_label = safe_text(form.get("bodyEssence"))
    brain_essence_label = safe_text(form.get("brainEssence"))
    body_state_label = safe_text(form.get("bodyState"))
    cog_state_label = safe_text(form.get("cogState"))
    job_state_label = safe_text(form.get("jobState"))
    readiness_label = safe_text(form.get("readiness"))
    support_label = safe_text(form.get("support"))
    environment_label = safe_text(form.get("environment"))

    goal_type = safe_text(form.get("goalType"))
    goal_text = safe_text(form.get("goalText"))
    life_type = safe_text(form.get("lifeType"))
    life_text = safe_text(form.get("lifeText"))
    concern_area = safe_text(form.get("concernArea"))
    concern_text = safe_text(form.get("concernText"))

    raw_core_essence_values = form.getlist("pastNature")
    raw_current_nature_values = form.getlist("currentNature")

    core_essences = parse_core_essences(raw_core_essence_values)
    current_natures = parse_current_natures(raw_current_nature_values)
    nature_items = build_nature_items(raw_current_nature_values)

    # '고민 없음'이어도 현실 조건은 지우지 않음.
    # 새 ra_model에서는 readiness/support/environment가 실제 계산 자원으로 쓰임.
    if concern_area == "고민 없음":
        concern_text = ""

    experiences = get_experiences_from_form(form)

    body_score = map_body_score(body_essence_label, body_state_label)
    brain_score = map_brain_score(brain_essence_label, cog_state_label)

    input_data = {
        "basic_info": {
            "name": safe_text(form.get("name")),
            "birth": birth,
            "age": age,
            "life_stage": life_stage,
            "gender": safe_text(form.get("gender")),
        },

        "origin": {
            "father": {
                "body_essence": "",
                "brain_essence": "",
                "nature": {"selected": [], "count": 0},
                "job": "",
            },
            "mother": {
                "body_essence": "",
                "brain_essence": "",
                "nature": {"selected": [], "count": 0},
                "job": "",
            },
        },

        "root": {
            "body_essence": body_essence_label,
            "brain_essence": brain_essence_label,
            "current_job": job_state_label,
            "nature": {
                "selected": current_natures,
                "count": len(current_natures),
            },
            "core_essence": {
                "selected": core_essences,
                "count": len(core_essences),
            },
        },

        "nature_change": {
            "past": {
                "selected": core_essences,
                "count": len(core_essences),
            },
            "current": {
                "selected": current_natures,
                "count": len(current_natures),
            },
            "selected_natures": current_natures,
            "items": nature_items,
        },

        "current_state": {
            "body_state": {
                "label": body_state_label,
                "score": BODY_STATE_SCORE.get(body_state_label, 0),
            },
            "cognitive_state": {
                "label": cog_state_label,
                "score": COG_STATE_SCORE.get(cog_state_label, 0),
            },
            "job_state": {
                "label": job_state_label,
                "score": JOB_STATE_SCORE.get(job_state_label, 0),
            },
            "body_essence_strength": {
                "label": body_state_label,
                "score": body_score,
            },
            "brain_essence_strength": {
                "label": cog_state_label,
                "score": brain_score,
            },
        },

        "experience_pattern": experiences,

        "direction_goal": {
            "current_direction": life_type,
            "current_direction_text": life_text,
            "current_direction_note": life_text,
            "current_goal_type": goal_type,
            "current_goal_text": goal_text,
            "current_goal_note": goal_text,
            "desired_life_note": life_text,
        },

        "main_concern": {
            "selected": concern_area,
            "detail": concern_text,
            "note": concern_text,
        },

        "reality_condition": {
            "readiness": {
                "label": readiness_label,
                "score": READINESS_SCORE.get(readiness_label, 0),
            },
            "support": {
                "label": support_label,
                "score": SUPPORT_SCORE.get(support_label, 0),
            },
            "environment": {
                "label": environment_label,
                "score": ENVIRONMENT_SCORE.get(environment_label, 0),
            },
        },

        "goal_history": {},

        "raw_labels": {
            "body_essence": body_essence_label,
            "body_state": body_state_label,
            "brain_essence": brain_essence_label,
            "cog_state": cog_state_label,
            "job_state": job_state_label,
            "readiness": readiness_label,
            "support": support_label,
            "environment": environment_label,
        }
    }

    return input_data


def has_meaningful_form_input(form) -> bool:
    if form.get("name", "").strip():
        return True
    if form.get("gender", "").strip():
        return True
    if form.get("job", "").strip():
        return True
    if form.get("environment_state", "").strip():
        return True
    if form.get("health_state", "").strip():
        return True

    if form.getlist("essence"):
        return True

    for key in [
        "nature_action",
        "nature_cognition",
        "nature_social",
        "nature_change",
        "nature_inner",
        "nature_decision",
        "nature_energy",
    ]:
        if form.getlist(key):
            return True

    if form.getlist("current_goal"):
        return True
    if form.getlist("experience_job[]"):
        return True
    if form.getlist("experience_field[]"):
        return True
    if form.getlist("experience_result[]"):
        return True
    if form.getlist("experience_reason[]"):
        return True

    return False


def has_minimum_required_inputs(input_data):
    missing = []

    if not input_data.get("name"):
        missing.append("이름")
    if not input_data.get("gender"):
        missing.append("성별")
    if not input_data.get("current_job"):
        missing.append("현재 직업")
    if not input_data.get("essences"):
        missing.append("본질")
    if not input_data.get("natures"):
        missing.append("본성")

    return (len(missing) == 0, missing)

def build_narrative_blocks(input_data, raw_result):
    """
    raw_result 안의 점수/라벨/경로 정보를 바탕으로
    사용자용 결과 문장 6개를 생성한다.
    """

    # -----------------------------
    # 1) 기본 재료 추출
    # -----------------------------
    name = pick_first_nonempty(
        input_data.get("name"),
        raw_result.get("name"),
        default="분석 대상"
    )

    root_score = raw_result.get("root_score", raw_result.get("final_root_score", 0))
    status_label = pick_first_nonempty(
        raw_result.get("root_label"),
        raw_result.get("status_label"),
        label_status_by_score(root_score)
    )

    # 강점/약점 영역
    strong_area = pick_first_nonempty(
        raw_result.get("top_opportunity"),
        raw_result.get("top_opportunity_label"),
        raw_result.get("strong_point"),
        default="현재 강점 본성"
    )

    weak_area = pick_first_nonempty(
        raw_result.get("top_threat"),
        raw_result.get("top_threat_label"),
        raw_result.get("weak_point"),
        default="보완이 필요한 본성"
    )

    # 핵심 문제
    core_problem = normalize_problem_label(
        pick_first_nonempty(
            raw_result.get("core_problem"),
            raw_result.get("top_threat"),
            raw_result.get("top_threat_label"),
            input_data.get("current_concern_note"),
            default="핵심 부담 영역"
        )
    )

    # HW / SW 해석용
    hw_score = raw_result.get("hw_score", 0)
    sw_score = raw_result.get("sw_score", 0)

    if hw_score >= sw_score + 8:
        balance_text = "기반은 비교적 버티고 있으나, 생각과 실행을 연결하는 힘이 상대적으로 약한 상태"
        formal_balance_text = "기반 안정성은 확보되어 있으나, 실천력이 상대적으로 부족한 상태"
    elif sw_score >= hw_score + 8:
        balance_text = "생각과 판단의 힘은 살아 있으나, 이를 안정적으로 받쳐 주는 기반이 충분히 따라주지 못하는 상태"
        formal_balance_text = "인지·판단 기반은 훌륭하나, 기반 안정성이 상대적으로 부족한 상태"
    else:
        balance_text = "기반과 실행 측면이 모두 크게 무너지지는 않지만, 아직 완전한 수렴 상태를 이루었다고 보기는 어려운 상태"
        formal_balance_text = "기반과 실천력은 출중하나, 근본의 하위 요소 간 수렴 상태가 완전히 안정되지는 않은 상태"

    # 미래 경로
    improve_prob = raw_result.get("improve_prob", raw_result.get("improvement_probability", 0))
    maintain_prob = raw_result.get("maintain_prob", raw_result.get("maintenance_probability", 0))
    decline_prob = raw_result.get("decline_prob", raw_result.get("decline_probability", 0))

    primary_key, vals = choose_primary_path(improve_prob, maintain_prob, decline_prob)
    secondary_key, secondary_value = choose_secondary_path(primary_key, vals)

    primary_label = path_label_user(primary_key)
    secondary_label = path_label_user(secondary_key)

    primary_pct = pct_text(vals[primary_key])
    secondary_pct = pct_text(secondary_value)

    # 권장 방향용
    recommendation_focus = pick_first_nonempty(
        raw_result.get("priority_target"),
        raw_result.get("priority_label"),
        weak_area,
        core_problem,
        default="가장 약한 본성"
    )

    # -----------------------------
    # 2) 한 줄 요약
    # -----------------------------
    one_line_summary = (
        f"{name}님의 현재 상태는 전반적으로 '{status_label}' 수준이며, "
        f"가장 큰 부담은 '{core_problem}'이고, 앞으로의 주된 흐름은 "
        f"'{primary_label}' 가능성({primary_pct}%) 쪽에 더 가깝습니다."  #{primary_pct:.1f}
    )

    # -----------------------------
    # 3) 현재 상태
    # -----------------------------
    current_status_text = (
        f"{name}님의 현재 상태는 전체적으로 '{status_label}' 수준으로 해석됩니다. "
        f"현재는 '{strong_area}' 선택 영역이 비교적 안정적으로 작용하고 있어 상황이 크게 흔들리지는 않지만, "
        f"{balance_text}입니다. "
        f"즉, 일부 강점은 분명 존재하나, 그것이 실제 변화와 성과로 완전히 이어지기 위해서는 "
        f"조금 더 조정과 보완이 필요한 단계로 볼 수 있습니다."
    )

    # -----------------------------
    # 4) 핵심 문제
    # -----------------------------
    core_problem_text = (
        f"현재 가장 크게 작용하는 부담은 '{core_problem}' 영역입니다. "
        f"이 문제는 단순한 걱정이나 일시적 불편이 아니라, 앞으로의 선택과 실행 속도, "
        f"심리적 안정, 관계 유지에 영향을 줄 수 있는 현실적 압력으로 보입니다. "
        f"따라서 이 부분을 방치하면 다른 강점이 있어도 전체 흐름이 기대만큼 살아나지 못할 수 있습니다."
    )

    # -----------------------------
    # 5) 미래 흐름
    # -----------------------------
    if primary_key == "improve":
        future_flow_text = (
            f"앞으로의 주된 흐름은 '{primary_label}' 가능성({primary_pct}%)이 가장 높게 나타납니다. "
            f"이는 이미 모든 문제가 해결되었다는 뜻이 아니라, 현재 강점을 유지하면서 "
            f"'{recommendation_focus}'을(를) 보완해 나갈 경우 점진적으로 더 나은 방향으로 이동할 수 있다는 의미입니다. "
            f"즉, 지금은 급격한 도약보다 본성 변화를 통해 개선 흐름을 키워갈 수 있는 구간으로 해석됩니다."
        )
    elif primary_key == "maintain":
        future_flow_text = (
            f"앞으로의 주된 흐름은 '{primary_label}' 가능성({primary_pct}%)이 가장 높게 나타납니다. "
            f"이는 현재 상태가 완전히 무너지는 상황은 아니지만, 뚜렷한 상승 전환이 약하다는 뜻입니다. "
            f"따라서 지금은 현 상태를 지키는 데 그치지 말고, '{recommendation_focus}' 영역을 조정하여 "
            f"정체를 완만한 개선 흐름으로 바꾸는 노력이 중요합니다."
        )
    else:
        future_flow_text = (
            f"앞으로의 주된 흐름은 '{primary_label}' 가능성({primary_pct}%)이 가장 높게 나타납니다. "
            f"이는 현재 상태에서 부담이 계속 누적될 경우, 일부 약한 본성이 전체 흐름을 끌어내릴 수 있음을 뜻합니다. "
            f"다만 이것은 확정된 악화 예측이 아니라, 현재의 부담을 제때 완화하지 못할 때 나타날 수 있는 경향입니다. "
            f"지금 적절히 변화를 추구하면 이 흐름은 충분히 극복될 여지가 있습니다."
        )

    # -----------------------------
    # 6) 보조 흐름
    # -----------------------------
    supplemental_path_text = (
        f"다만 현재 흐름이 한 방향으로만 고정된 것은 아닙니다. "
        f"보조적으로는 '{secondary_label}' 가능성({secondary_pct})도 함께 존재합니다. "
        f"이는 작은 환경 변화나 판단 차이, 실행 강도의 차이에 따라 결과 경로가 달라질 수 있음을 의미합니다. "
        f"따라서 지금 단계에서는 낙관이나 비관을 단정하기보다, "
        f"전체 흐름을 안정적으로 관리하고, 약한 본성을 조정하는 노력이 더 중요합니다."
    )

    # -----------------------------
    # 7) 권장 방향
    # -----------------------------
    recommendation_text = (
        f"지금은 무리하게 큰 변화를 한꺼번에 시도하기보다, "
        f"'{recommendation_focus}' 영역을 먼저 안정시키는 것이 더 중요합니다. "
        f"현재 강점인 '{strong_area}'은(는) 유지하되, 가장 약하게 작용하는 본성을 차분히 보완해야 "
        f"전체 흐름이 흔들리지 않고 안정적인 흐름으로 넘어갈 수 있습니다. "
        f"즉, 지금의 권장 방향은 '강점 유지 + 약점 보완 + 흐름 안정화'의 순서로 접근하는 것입니다."
    )

    return {
        "one_line_summary": one_line_summary,
        "current_status_text": current_status_text,
        "core_problem_text": core_problem_text,
        "future_flow_text": future_flow_text,
        "supplemental_path_text": supplemental_path_text,
        "recommendation_text": recommendation_text,

        # 내부 점검용
        "formal_balance_text": formal_balance_text,
        "primary_path_key": primary_key,
        "secondary_path_key": secondary_key,
    }

def analyze_nature_patterns(natures: list[str]) -> dict:
    """
    본성 자동 해석 로직
    - 강점 본성
    - 부담 본성
    - 상충 본성
    - 개인화 권고 재료 생성
    """

    natures = natures or []
    nset = set(natures)

    strengths = []
    risks = []
    conflicts = []

    # -----------------------------
    # 1. 개별 본성 패턴 해석
    # -----------------------------
    pattern_map = {
        "추진성": {
            "strength": "일을 앞으로 밀고 가는 힘이 있습니다.",
            "risk": "추진 속도가 빨라지면, 주변 조건을 충분히 살피지 못할 수 있습니다.",
            "advice": "추진하기 전에 우선순위와 감당 범위를 먼저 조정하는 것이 좋습니다.",
        },
        "주도성": {
            "strength": "스스로 방향을 정하고 이끌어가려는 힘이 있습니다.",
            "risk": "혼자 책임을 많이 떠안거나, 타인의 지원 속도와 어긋날 수 있습니다.",
            "advice": "주도하되, 중간 점검과 역할 분담을 함께 염두에 두는 것이 좋습니다.",
        },
        "확장형": {
            "strength": "새로운 가능성을 넓히고 기회를 찾는 힘이 있습니다.",
            "risk": "방향이 많아지면 활력이 분산될 수 있습니다.",
            "advice": "확장보다 먼저 한 가지 핵심 방향을 정해 집중하는 것이 좋습니다.",
        },
        "욕구강조": {
            "strength": "추진하고자 하는 방향이 분명하고 동기가 강하게 작용합니다.",
            "risk": "욕구가 앞서면 현실 조건이나 관계 부담을 놓칠 수 있습니다.",
            "advice": "하고 싶은 일과 지금 가능한 일을 구분하는 것이 필요합니다.",
        },
        "감정 변동성": {
            "strength": "상황과 감정 변화에 민감하게 반응하는 감수성이 있습니다.",
            "risk": "감정 흐름이 커지면 판단과 실행이 흔들릴 수 있습니다.",
            "advice": "중요한 결정은 감정이 가라앉은 뒤 다시 실행하는 방식이 좋습니다.",
        },
        "회피형": {
            "strength": "위험을 피하고 부담을 줄이려는 방어 감각이 있습니다.",
            "risk": "결정과 실행이 늦어져 기회를 놓칠 수 있습니다.",
            "advice": "큰 결정보다 작은 실행부터 시작하는 것이 좋습니다.",
        },
        "신중형": {
            "strength": "위험을 검토하고 실수를 줄이는 힘이 있습니다.",
            "risk": "검토가 길어지면 실행 시점이 늦어질 수 있습니다.",
            "advice": "완벽한 판단보다 70% 확신에서 작은 실행을 시작하는 것이 좋습니다.",
        },
        "전략형": {
            "strength": "상황을 구조적으로 보고 방향을 설계하는 힘이 있습니다.",
            "risk": "생각이 복잡해지면 실행보다 계산이 앞설 수 있습니다.",
            "advice": "전략을 짧은 실행 단위로 나누는 것이 좋습니다.",
        },
        "고활력형": {
            "strength": "활력과 활동성이 높아 빠르게 움직일 수 있습니다.",
            "risk": "과하게 달리면 피로가 누적될 수 있습니다.",
            "advice": "활동량보다 회복 리듬을 함께 관리하는 것이 좋습니다.",
        },
        "저활력형": {
            "strength": "무리하지 않고 활력을 아끼는 흐름이 있습니다.",
            "risk": "필요한 실행도 미뤄질 수 있습니다.",
            "advice": "짧고 작은 단위의 반복 실행이 더 적합합니다.",
        },
        "관계지향": {
            "strength": "사람과의 연결을 중시하고 관계를 살리는 힘이 있습니다.",
            "risk": "타인의 기대를 지나치게 의식하면 자기 방향이 약해질 수 있습니다.",
            "advice": "관계를 유지하되, 자신의 우선순위를 먼저 정하는 것이 좋습니다.",
        },
        "관계융화": {
            "strength": "갈등을 줄이고 분위기를 조율하는 힘이 있습니다.",
            "risk": "조화를 중시하다 보면 필요한 결정을 미룰 수 있습니다.",
            "advice": "맞추는 것과 결정하는 것을 구분하는 것이 좋습니다.",
        },
        "분석형": {
            "strength": "상황을 따져보고 원인을 찾는 힘이 있습니다.",
            "risk": "분석이 길어지면 실행이 늦어질 수 있습니다.",
            "advice": "분석 결과를 바로 하나의 실행으로 연결하는 것이 좋습니다.",
        },
        "탐구형": {
            "strength": "깊이 파고들고 원리를 찾는 힘이 있습니다.",
            "risk": "탐색이 길어지면 현실 실행과 거리가 생길 수 있습니다.",
            "advice": "탐구 결과를 실제 적용 과제로 바꾸는 것이 좋습니다.",
        },
        "안정지향": {
            "strength": "기반을 지키고 위험을 줄이는 힘이 있습니다.",
            "risk": "변화가 필요한 시점에도 익숙한 습관에 머물 수 있습니다.",
            "advice": "안정을 유지하되 작은 변화부터 허용하는 것이 좋습니다.",
        },
        "변화지향": {
            "strength": "새로운 흐름을 받아들이고 전환하려는 힘이 있습니다.",
            "risk": "변화가 잦으면 지속성이 약해질 수 있습니다.",
            "advice": "변화 방향을 하나로 정하고, 일정 기간 유지하는 것이 좋습니다.",
        },
    }

    for n in natures:
        info = pattern_map.get(n)
        if not info:
            continue
        strengths.append(f"{n}: {info['strength']}")
        risks.append(f"{n}: {info['risk']}")

    # -----------------------------
    # 2. 상충 본성 탐지
    # -----------------------------
    conflict_rules = [
        {
            "pair": ("추진성", "회피형"),
            "text": "추진하려는 힘과 피하려는 힘이 함께 작용하여, 마음은 앞서 가지만 실제 실행은 늦어질 수 있습니다.",
            "advice": "큰 결정을 미루기보다, 부담이 적은 작은 실행부터 시작하는 것이 좋습니다.",
        },
        {
            "pair": ("확장형", "안정지향"),
            "text": "넓히고 싶은 성향과 지키고 싶은 성향이 함께 있어, 확장과 안정 사이에서 갈등이 생길 수 있습니다.",
            "advice": "새로운 확장은 하되, 기존 기반을 해치지 않는 범위부터 정하는 것이 좋습니다.",
        },
        {
            "pair": ("확장형", "욕구강조"),
            "text": "하고 싶은 방향이 많아지고 욕구도 강해져, 활력이 여러 방향으로 분산될 수 있습니다.",
            "advice": "지금 가장 중요한 한 가지 목표를 정하고 나머지는 보류하는 것이 좋습니다.",
        },
        {
            "pair": ("감정 변동성", "전략형"),
            "text": "전략적으로 판단하려는 힘과 감정 변화가 함께 작용하여, 판단은 있어도 실행 리듬이 흔들릴 수 있습니다.",
            "advice": "중요한 판단은 감정이 흔들리는 순간보다 안정된 시간에 다시 정리하는 것이 좋습니다.",
        },
        {
            "pair": ("신중형", "추진성"),
            "text": "빨리 추진하려는 힘과 조심스럽게 검토하려는 힘이 함께 있어, 실행 속도에 내부 충돌이 생길 수 있습니다.",
            "advice": "검토 시간을 정해두고, 그 이후에는 작은 실행으로 넘기는 방식이 좋습니다.",
        },
        {
            "pair": ("관계지향", "주도성"),
            "text": "관계를 살피려는 성향과 주도하려는 성향이 함께 있어, 타인의 반응과 자신의 방향 사이에서 부담이 생길 수 있습니다.",
            "advice": "관계는 살피되 최종 기준은 자신의 핵심 방향에 두는 것이 좋습니다.",
        },
        {
            "pair": ("관계융화", "욕구강조"),
            "text": "타인과 맞추려는 성향과 자신의 욕구를 밀고 가려는 성향이 함께 있어, 관계 속에서 피로가 생길 수 있습니다.",
            "advice": "양보할 것과 반드시 지킬 것을 먼저 구분하는 것이 좋습니다.",
        },
        {
            "pair": ("고활력형", "감정 변동성"),
            "text": "활동성이 높고 감정 반응도 커서, 순간적으로 몰입했다가 쉽게 지칠 수 있습니다.",
            "advice": "실행 강도보다 회복 리듬을 함께 설계하는 것이 좋습니다.",
        },
        {
            "pair": ("저활력형", "확장형"),
            "text": "하고 싶은 방향은 넓지만, 실제 활동은 제한되어, 계획과 실행 사이에 차이가 생길 수 있습니다.",
            "advice": "확장 목표를 줄이고, 작게 반복 가능한 상태로 바꾸는 것이 좋습니다.",
        },
    ]

    for rule in conflict_rules:
        a, b = rule["pair"]
        if a in nset and b in nset:
            conflicts.append(rule)

    return {
        "strengths": strengths,
        "risks": risks,
        "conflicts": conflicts,
    }


def build_nature_change_text(input_data: dict, result: dict) -> str:
    """
    본성 변화 기반 개인화 권고
    - 본질은 기준
    - 본성은 환경 속에서 변하고 작동하는 흐름
    - 상충 본성, 부담 본성, 강점 본성을 연결해 행동 권고 생성
    """

    natures = (
        input_data.get("root", {})
        .get("nature", {})
        .get("selected", [])
    ) or input_data.get("natures", []) or []

    essences = (
        input_data.get("root", {})
        .get("core_essence", {})
        .get("selected", [])
    ) or input_data.get("essences", []) or []

    path_decision = safe_text(result.get("path_decision"))
    threat_vectors = result.get("threat_vectors", []) or []
    opportunity_vectors = result.get("opportunity_vectors", []) or []

    analysis = analyze_nature_patterns(natures)

    strengths = analysis.get("strengths", [])
    risks = analysis.get("risks", [])
    conflicts = analysis.get("conflicts", [])

    lines = []

    # -----------------------------
    # 1. RA 원칙 설명
    # -----------------------------
    essence_text = ", ".join(essences[:3]) if essences else "핵심 본질"
    nature_text = ", ".join(natures[:2]) if natures else "현재 본성"

    lines.append(
        f"근본 분석에서 {essence_text}은 바꾸어야 할 대상이 아니라 판단의 기준입니다. "
        f"실제 변화와 미래 흐름은 현재 환경 속에서 {nature_text}이 어떻게 작용하느냐에 따라 달라집니다."
    )

    # -----------------------------
    # 2. 상충 본성 우선 출력
    # -----------------------------
    if conflicts:
        top_conflict = conflicts[0]
        lines.append(
            f"현재 가장 먼저 살펴볼 본성 흐름은 {top_conflict['text']} 입니다. "
            f"따라서 {top_conflict['advice']}"
        )
    elif risks:
        lines.append(
            f"현재 주의할 본성 흐름은 {risks[0]} 입니다. "
            "이 부분은 성격 자체의 문제가 아니라, 현재 조건에서 특정 성향이 과하게 작용할 때 생기는 부담입니다."
        )
    else:
        lines.append(
            "현재 본성 흐름에서 뚜렷한 상충은 강하게 드러나지 않습니다. "
            "다만 강점이 과하게 작용하지 않도록 속도와 범위를 조절하는 것이 좋습니다."
        )

    # -----------------------------
    # 3. 살릴 강점
    # -----------------------------
    if strengths:
        lines.append(
            f"반대로 {strengths[0]} 본성은 중요한 강점으로 작용합니다. 상황을 객관적으로 살펴보고 방향을 정리하는데 도움이 됩니다."
            "이 성향은 억누르기보다 방향을 정해 적용해가는 편이 좋습니다."
        )

    # -----------------------------
    # 4. 위협/기회 벡터와 연결
    # -----------------------------
    if threat_vectors:
        top_threat = threat_vectors[0]
        factor = safe_text(top_threat.get("factor"))
        if factor:
            lines.append(
                f"현재 위협 요인으로 나타난 '{factor}' 역시 본성이 실제 행동으로 이어지는 방식과 연결됩니다. "
                "따라서 문제를 외부 조건만으로 보지 말고, 자신의 행동 패턴이 이 부담을 키우고 있는지 살펴야 합니다."
            )

    if opportunity_vectors:
        top_opp = opportunity_vectors[0]
        factor = safe_text(top_opp.get("factor"))
        if factor:
            lines.append(
                f"기회 요인으로 나타난 '{factor}'은 현재 본성을 활용하면 잘 살릴 수 있는 흐름입니다."
            )

    # -----------------------------
    # 5. 미래 흐름별 최종 행동 권고
    # -----------------------------
    if "위협" in path_decision:
        lines.append(
            "따라서 지금은 한가지 목표만 선택하고, 나머지는 잠시 보류하는 것도 참작하면 좋습니다. "
            "본성을 억누르기보다, 과하게 영향을 미치는 성향의 속도를 낮추고 한 가지 실행 기준을 세우는 것이 필요합니다."
        )
    elif "개선" in path_decision:
        lines.append(
            "현재는 본성의 강점이 성과로 이어질 가능성이 있는 구간입니다. "
            "다만 여러 방향으로 넓히기보다, 가장 잘 맞는 한 방향을 정해 반복 실행하는 것이 좋습니다."
        )
    elif "유지" in path_decision:
        lines.append(
            "현재는 큰 변화보다 안정적인 유지가 더 적합합니다. "
            "익숙한 강점은 유지하되, 반복적으로 부담을 만드는 행동 패턴만 조금씩 줄이는 것이 좋습니다."
        )
    else:
        lines.append(
            "현재는 강점과 부담이 함께 나타나는 혼합 흐름입니다. "
            "강점은 유지하고, 과하게 작용하는 본성은 속도와 범위를 조절하는 방식이 적합합니다."
        )

    lines.append(
        "👉 지금 바로 실행:\n"
        "→ 한 가지 목표만 선택하고, 나머지는 잠시 보류"
    )

    # build_nature_change_text 마지막에 추가
    action_line = build_action_summary(natures, path_decision)
    lines.append(action_line)

    return "\n\n".join(lines)

def build_action_summary(natures: list[str], path_decision: str) -> str:
    nset = set(natures or [])

    # 1. 본성 기반 우선 판단
    if "확장형" in nset and "욕구강조" in nset:
        return "👉 지금은 한 가지 목표만 선택하고 나머지는 잠시 보류하세요"

    if "추진성" in nset and "회피형" in nset:
        return "👉 큰 결정보다 바로 할 수 있는 작은 행동 하나부터 시작하세요"

    if "감정 변동성" in nset:
        return "👉 중요한 결정은 감정이 안정된 후에 다시 판단하세요"

    if "저활력형" in nset:
        return "👉 부담 없는 작은 단위로 나누어 반복 실행하세요"

    # 2. 경로 기반 fallback
    if "위협" in path_decision:
        return "👉 지금은 속도를 낮추고 한 가지 기준에 집중하세요"
    elif "개선" in path_decision:
        return "👉 한 방향을 정해 반복 실행을 시작하세요"
    elif "유지" in path_decision:
        return "👉 현재 방식을 유지하면서 무리한 변화는 피하세요"

    return "👉 지금 가장 중요한 한 가지에 집중하세요"

# =========================================================
# 5. 결과 후처리
# =========================================================
def post_process_result(input_data: dict, raw_result: dict) -> dict:
    if not isinstance(raw_result, dict):
        return {
            "engine": "RAIS",
            "one_line_summary": "분석 결과를 생성하지 못했습니다.",
            "current_status_text": "결과 형식이 올바르지 않습니다.",
            "core_problem_text": "입력값과 엔진 연결 상태를 점검해 주세요.",
            "future_flow_text": "미래 흐름이 아직 생성되지 않았습니다.",
            "supplemental_path_text": "보조 흐름이 아직 생성되지 않았습니다.",
            "recommendation_text": "권장 방향을 생성하지 못했습니다.",
        }

    result = dict(raw_result)

    # -----------------------------------------------------
    # 1) 이름 보호: input_data의 실제 이름이 있으면 유지
    # -----------------------------------------------------
    input_name = safe_text(input_data.get("name"))
    raw_name = safe_text(result.get("name"))

    if input_name:
        result["name"] = input_name
    elif raw_name:
        result["name"] = raw_name

    # -----------------------------------------------------
    # 2) narrative는 "빈 항목만" 보완하도록 사용
    #    기존 raw_result 문장을 절대 덮어쓰지 않음
    # -----------------------------------------------------
    try:
        narrative = build_narrative_blocks(input_data, result)

        if isinstance(narrative, dict):
            for key, value in narrative.items():
                if not safe_text(result.get(key)) and safe_text(value):
                    result[key] = value
        # 🔥 NEW: 본성 변화 권고 추가
        if not safe_text(result.get("nature_change_text")):
            result["nature_change_text"] = build_nature_change_text(input_data, result)

    except Exception as e:
         print("DEBUG narrative generation error:", e)

    # -----------------------------------------------------
    # 3) 최종 안전 fallback
    # -----------------------------------------------------
    if not safe_text(result.get("engine")):
        result["engine"] = "RAIS"

    if not safe_text(result.get("one_line_summary")):
        result["one_line_summary"] = "한 줄 요약이 아직 생성되지 않았습니다."

    if not safe_text(result.get("current_status_text")):
        result["current_status_text"] = "현재 상태 해석이 아직 생성되지 않았습니다."

    if not safe_text(result.get("core_problem_text")):
        result["core_problem_text"] = "핵심 문제가 아직 생성되지 않았습니다."

    if not safe_text(result.get("future_flow_text")):
        result["future_flow_text"] = "미래 흐름이 아직 생성되지 않았습니다."

    if not safe_text(result.get("supplemental_path_text")):
        result["supplemental_path_text"] = "보조 흐름 참고가 아직 생성되지 않았습니다."

    if not safe_text(result.get("recommendation_text")):
        result["recommendation_text"] = "권장 방향이 아직 생성되지 않았습니다."

    if not safe_text(result.get("nature_change_text")):
        result["nature_change_text"] = "본성 변화 권고가 아직 생성되지 않았습니다."

    return result


# =========================================================
# 6. fallback
# =========================================================
def build_fallback_result(input_data: dict) -> dict:
    name = safe_text(input_data.get("basic_info", {}).get("name")) or "분석 대상"
    concern = safe_text(input_data.get("main_concern", {}).get("selected")) or "현재 고민"
    goal_type = safe_text(input_data.get("direction_goal", {}).get("current_goal_type")) or "현재 목표"

    return {
        "engine": "Root Analysis Intelligence System (RAIS) fallback",
        "root_score": 50.0,
        "hw_score": 50.0,
        "sw_score": 50.0,
        "root_state": {
            "stability": 50.0,
            "health": 50.0,
            "execution": 50.0,

            "hw_score": 50.0,
            "sw_score": 50.0,
            "root_score": 50.0,
            "hw_label": "보통",
            "sw_label": "보통",
            "root_label": "보통",
        },
        "origin_root_alignment": {
            "total_alignment": 50.0,
            "interpretation": "기본 해석 모드",
        },
        "threat_vectors": [
            {
                "factor": f"현재 고민 압력: {concern}",
                "score": 10.0,
                "rationale": "현재 고민이 핵심 부담 요인으로 작용할 수 있습니다.",
            }
        ],
        "opportunity_vectors": [
            {
                "factor": f"핵심 목표: {goal_type}",
                "score": 10.0,
                "rationale": "목표 의식은 현재 상태를 유지하는 기반이 됩니다.",
            }
        ],
        "path_distribution": {
            "개선 경로": 45.0,
            "완만 개선": 0.0,
            "유지 경로": 55.0,
            "완만 위협": 0.0,
            "위협 경로": 0.0,
        },
        "state_transition": [
            {
                "rank": 1,
                "title": "유지 경로",
                "probability": 0.55,
                "probability_pct": 55.0,
                "summary": "현재 상태를 유지하는 흐름",
                "rationale": "급격한 변화보다 현재 상태를 조정하는 방향이 더 현실적입니다.",
            },
            {
                "rank": 2,
                "title": "개선 경로",
                "probability": 0.45,
                "probability_pct": 45.0,
                "summary": "보완 후 개선되는 흐름",
                "rationale": "취약 요인을 보완하면 상태 개선 가능성이 보입니다.",
            },
        ],
        "structural_conflicts": [],
        "future_pressures": [],
        "choice_points": [],
        "intervention_plan": [
            {
                "target": "핵심 상태 보완 전략",
                "action": "취약 요인을 먼저 정리합니다.",
                "reason": "현재 부담을 줄여야 다음 단계가 가능합니다.",
            }
        ],
        "influence_flow": {
            "simulations": [],
            "best_summary": "기본 해석 모드에서는 개입 시뮬레이션이 생략됩니다.",
        },
        "one_line_summary": f"{name}님의 현재 상태는 보완이 필요한 단계입니다.",
        "current_status_text": "기본 해석 모드로 전환되었습니다. 입력 상태로 들어왔으나 일부 처리에서 오류가 발생했습니다.",
        "core_problem_text": f"현재 가장 먼저 다루어야 할 문제는 '{concern}'입니다.",
        "future_flow_text": "당장은 급격한 변화보다 현재 상태를 정리하고 보완하는 흐름이 더 현실적입니다.",
        "recommendation_text": "취약한 부분을 먼저 보완하면서 현재 강점을 유지하는 방향이 바람직합니다.",
    }

# =========================================================
# 7. 디버그
# =========================================================
def print_debug_logs(raw_form_data: dict, input_data: dict, result: Any) -> None:
    print("\n" + "=" * 72)
    print("===== RAW FORM DATA =====")
    print(pformat(raw_form_data, sort_dicts=False, width=120))

    print("\n===== STRUCTURED INPUT DATA =====")
    print(pformat(input_data, sort_dicts=False, width=120))

    print("\n===== RA RESULT =====")
    print(pformat(result, sort_dicts=False, width=120))

    print("\n===== QUICK CHECK =====")
    print(f"name                    : {input_data['basic_info']['name']}")
    print(f"birth                   : {input_data['basic_info']['birth']}")
    print(f"age                     : {input_data['basic_info']['age']}")
    print(f"life_stage              : {input_data['basic_info']['life_stage']}")
    print(f"gender                  : {input_data['basic_info']['gender']}")
    print(f"body_essence            : {input_data['root']['body_essence']}")
    print(f"brain_essence           : {input_data['root']['brain_essence']}")
    print(f"core_essence_count      : {input_data['root']['core_essence']['count']}")
    print(f"current_nature_count    : {input_data['root']['nature']['count']}")
    print(f"job_state               : {input_data['current_state']['job_state']['label']}")
    print(f"body_state              : {input_data['current_state']['body_state']['label']}")
    print(f"cognitive_state         : {input_data['current_state']['cognitive_state']['label']}")
    print(f"goal_type               : {input_data['direction_goal']['current_goal_type']}")
    print(f"goal_text               : {input_data['direction_goal']['current_goal_text']}")
    print(f"life_type               : {input_data['direction_goal']['current_direction']}")
    print(f"life_text               : {input_data['direction_goal']['current_direction_text']}")
    print(f"main_concern            : {input_data['main_concern']['selected']}")
    print(f"main_concern_detail     : {input_data['main_concern']['detail']}")
    print(f"readiness               : {input_data['reality_condition']['readiness']['label']}")
    print(f"support                 : {input_data['reality_condition']['support']['label']}")
    print(f"environment             : {input_data['reality_condition']['environment']['label']}")
    print(f"experience_count        : {len(input_data['experience_pattern'])}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    # app.run(debug=False)  #True)
    app.run(host="127.0.0.1", port=6060, debug=False)