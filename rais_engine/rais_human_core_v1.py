from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple, Optional

# =========================================================
# RA MODEL
# Root Analysis engine (full draft)
# - Origin(Essence) -> Nature -> Root -> Talent/Jobs
# - UI-independent, alias-tolerant input parser
# - Can be connected later to Flask / index.html
# =========================================================

MODEL_VERSION = "RA_MODEL_v1_draft_2026_04_30_flow3_ra_style"


# =========================================================
# 0. 기본 유틸
# =========================================================

def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def avg(values: List[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if isinstance(v, (int, float))]
    if not vals:
        return default
    return sum(vals) / len(vals)


def normalize_score(value: Any, default: float = 50.0) -> float:
    if isinstance(value, (int, float)):
        return clamp(float(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return clamp(float(text))
        except ValueError:
            lowered = text.lower()
            mapping = {
                "매우 낮음": 15,
                "낮음": 30,
                "다소 낮음": 40,
                "보통": 50,
                "중간": 50,
                "다소 높음": 60,
                "높음": 75,
                "매우 높음": 90,
                "yes": 70,
                "no": 30,
                "true": 70,
                "false": 30,
            }
            return mapping.get(text, mapping.get(lowered, default))
    if isinstance(value, bool):
        return 70.0 if value else 30.0
    return default


def score_to_label(score: float) -> str:
    if score > 85:
        return "매우 안정"
    if score >= 65:
        return "안정"
    if score >= 35:
        return "다소 안정"
    if score >= 15:
        return "다소 불안정"
    return "매우 불안정"


def top_n_items(score_map: Dict[str, float], n: int = 3) -> List[Tuple[str, float]]:
    return sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:n]


def bottom_n_items(score_map: Dict[str, float], n: int = 3) -> List[Tuple[str, float]]:
    return sorted(score_map.items(), key=lambda x: x[1])[:n]


def safe_text(x: Any, default: str = "") -> str:
    if x is None:
        return default
    return str(x).strip()


def flatten_selected(value: Any) -> List[str]:
    """
    dict/list/string 형태를 모두 허용하여 문자열 목록으로 평탄화.
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("\n", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(value, dict):
        result = []
        for k, v in value.items():
            if isinstance(v, bool) and v:
                result.append(str(k))
            elif isinstance(v, (int, float)) and v > 0:
                result.append(str(k))
            elif isinstance(v, str) and v.strip():
                result.append(str(k))
        return result
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten_selected(item))
        return out
    return [str(value)]


def get_first(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
    return default


# =========================================================
# 1. 핵심 정의
# =========================================================

ESSENCE_KEYS = [
    "적응성", "학습성", "관계성", "표현성", "추진성", "안전성", "반응성",
    "남성성", "여성성",
]

ESSENCE_CODE_MAP = {
    "adaptability": "적응성",
    "learning": "학습성",
    "relation": "관계성",
    "expression": "표현성",
    "drive": "추진성",
    "safety": "안전성",
    "reaction": "반응성",
    "masculinity": "남성성",
    "femininity": "여성성",
}

STATE_SCORE_MAP = {
    "very_poor": 20,
    "poor": 35,
    "trying": 50,
    "hopeful": 65,
    "ready": 80,

    "strong": 80,
    "vital": 70,
    "normal": 55,
    "weak": 40,
    "ill": 25,
}

GOAL_CODE_MAP = {
    "family_peace": "가정 평화",
    "health_recovery": "건강 회복",
    "economic_stability": "경제적 안정",
    "performance_jump": "성과 도약",
    "life_margin": "삶의 여유",
    "social_contribution": "사회 기여",
    "social_recognition": "사회적 인정",
    "relationship_improvement": "관계 개선",
    "personality_change": "성격 변화",
    "keep_job": "현 직업 유지",
    "new_job": "새 직업 탐색",
    "no_worry": "고민 없음",
}

ROOT_KEYS = ["stability", "drive", "cognition", "relation"]

TALENT_AXES = [
    "연구·분석형",
    "전략·참모형",
    "실행·사업형",
    "관계·중재형",
    "표현·창작형",
    "관리·안정형",
    "감지·직관형",
]

JOB_GROUPS = {
    "연구·분석형": {
        "jobs": ["연구원", "분석가", "데이터/정책 분석", "기획자", "컨설턴트", "교수/강의", "전문 평가/심사", "조사/분석 기획", "전략가"],
        "caution": "즉흥 대응만 많은 현장 영업, 감정 소모 중심 서비스직",
    },
    "전략·참모형": {
        "jobs": ["전략기획", "정책기획", "자문", "조직 설계", "보좌/참모", "중장기 기획", "사업 기획", "운영 전략 설계"],
        "caution": "반복 단순 업무만 지속되는 구조, 판단권 없는 소모성 역할",
    },
    "실행·사업형": {
        "jobs": ["사업가", "영업 리더", "프로젝트 리더", "운영 총괄", "현장 책임자", "추진형 관리자", "개척형 역할", "성과 중심 실무"],
        "caution": "지나치게 정적인 역할, 결정권 없이 유지 업무만 반복되는 구조",
    },
    "관계·중재형": {
        "jobs": ["상담", "코칭", "교육", "HR", "협상", "조직 조정", "커뮤니티 운영", "대외 협력", "고객 관계 관리"],
        "caution": "고립적 단독 연구만 지속되는 구조, 지나치게 비인간적/무관계적 업무",
    },
    "표현·창작형": {
        "jobs": ["작가", "디자이너", "콘텐츠 제작", "예술/문화 기획", "브랜딩", "스토리텔링", "강연/표현형", "교육", "홍보 콘텐츠 기획"],
        "caution": "지나치게 경직된 반복 행정, 창의성 발휘가 거의 없는 구조",
    },
    "관리·안정형": {
        "jobs": ["행정", "운영", "관리", "재무/회계", "품질 관리", "유지보수", "자원 관리", "프로세스 운영", "안정화 역할"],
        "caution": "불확실성과 즉흥성이 지나치게 큰 구조, 매일 방향이 바뀌는 혼란한 역할",
    },
    "감지·직관형": {
        "jobs": ["리스크 감지", "위기 대응 보조", "모니터링", "상황 판단 지원", "기획 보조", "탐지/관찰형 업무", "조기 경보 역할", "패턴 파악 업무"],
        "caution": "과도한 성과 압박 영업, 구조화 없는 장기 반복 행정",
    },
}

ESSENCE_NATURE_MAP: Dict[str, Dict[str, float]] = {
    "적응성": {
        "변화지향성": 1.00, "확장형": 0.95, "유연성": 0.95, "위험 감수성": 0.80,
        "새로운 시도 성향": 0.90, "회복 탄력성": 0.90,
        "능동성": 0.75, "도전성": 0.55,
        "직관력": 0.45, "탐구성": 0.50,
    },
    "학습성": {
        "분석력": 1.00, "논리성": 0.95, "탐구성": 0.95, "판단력": 0.85,
        "전략성": 0.80, "기억 유지력": 0.80, "이해력": 0.70,
        "창의성": 0.45, "집중성": 0.55, "집중력": 0.55, "언어 표현력": 0.35, "직관력": 0.45,
    },
    "관계성": {
        "관계지향": 1.00, "공감성": 0.95, "관계융화": 0.95, "소통성": 0.90,
        "영향력": 0.80, "포용성": 0.85,
        "표현력": 0.65, "이해력": 0.80, "자기주장": 0.45,
        "배려성": 0.70, "협력성": 0.70, "감정 읽기": 0.75,
    },
    "표현성": {
        "표현력": 1.00, "언어 표현력": 1.00, "감정 표현성": 0.95, "창의성": 0.90, "발신성": 0.85,
        "설득성": 0.80, "존재감": 0.75, "자기주장": 0.55,
        "영향력": 0.50, "소통성": 0.45, "자신감": 0.40,
    },
    "추진성": {
        "실행성": 1.00, "도전성": 0.95, "추진력": 0.95, "주도성": 0.90,
        "책임감": 0.80, "능동성": 0.85, "경쟁성": 0.80, "결단형": 0.85, "결단력": 0.85,
        "전략성": 0.45, "집중성": 0.50, "집중력": 0.50, "지속성": 0.55,
    },
    "안전성": {
        "안정지향성": 1.00, "신중성": 0.95, "보수성": 0.85, "위험회피성": 0.80,
        "지속성": 0.90, "자기관리성": 0.85,
        "관계조율성": 0.45, "책임감": 0.50, "긴장 민감성": 0.40,
    },
    "반응성": {
        "직관력": 1.00, "감각 민감도": 0.95, "감정 민감성": 0.90, "즉각 반응성": 0.85,
        "상황 감지력": 0.90, "감정변동성": 0.55, "스트레스민감성": 0.45, "비교민감성": 0.35,
        "불안민감성": 0.45, "창의성": 0.40, "공감성": 0.45,
    },
    "남성성": {
        "구조 관심": 0.80, "논리성": 0.70, "집중력": 0.70, "실행성": 0.70,
        "경쟁성": 0.60, "주도성": 0.60, "능동성": 0.60, "결단력": 0.50,
        "공간/구조 사고": 0.75, "집중 지속성": 0.65, "도전성": 0.45,
    },
    "여성성": {
        "공감성": 0.80, "관계지향": 0.80, "언어 이해/표현": 0.80, "감정 민감성": 0.70,
        "포용성": 0.70, "배려성": 0.70, "유연성": 0.60, "회복 탄력성": 0.60,
        "감정 읽기": 0.60, "기억 유지력": 0.55, "관계조율성": 0.55,
        "섬세성": 0.70, "다중 과제 처리 성향": 0.65,
    },
}

# 본질이 Root에 직접 보정하는 기본값
ESSENCE_ROOT_BONUS: Dict[str, Dict[str, float]] = {
    "적응성": {"drive": 4, "cognition": 3},
    "학습성": {"cognition": 8},
    "관계성": {"relation": 8},
    "표현성": {"relation": 3, "cognition": 2},
    "추진성": {"drive": 9},
    "안전성": {"stability": 9},
    "반응성": {"cognition": 2, "relation": 2, "stability": 2},
    "남성성": {"drive": 3, "cognition": 3},
    "여성성": {"relation": 3, "stability": 3},
}

# 지능/재능 축과 본질 연결
ESSENCE_TALENT_MAP: Dict[str, Dict[str, float]] = {
    "학습성": {"연구·분석형": 1.0, "전략·참모형": 0.6},
    "관계성": {"관계·중재형": 1.0},
    "표현성": {"표현·창작형": 1.0, "관계·중재형": 0.35},
    "추진성": {"실행·사업형": 1.0},
    "안전성": {"관리·안정형": 1.0},
    "적응성": {"전략·참모형": 0.8, "실행·사업형": 0.35},
    "반응성": {"감지·직관형": 1.0, "전략·참모형": 0.25},
    "남성성": {"실행·사업형": 0.35, "연구·분석형": 0.20},
    "여성성": {"관계·중재형": 0.30, "표현·창작형": 0.20, "관리·안정형": 0.20},
}

# 본성(표현 방식)이 지능/재능 축을 보정
NATURE_TALENT_BOOST: Dict[str, Dict[str, float]] = {
    "분석력": {"연구·분석형": 1.0},
    "탐구성": {"연구·분석형": 0.9},
    "논리성": {"연구·분석형": 0.8, "전략·참모형": 0.3},
    "전략성": {"전략·참모형": 1.0, "연구·분석형": 0.4},
    "판단력": {"전략·참모형": 0.8},
    "주도성": {"실행·사업형": 0.9},
    "도전성": {"실행·사업형": 0.9},
    "실행성": {"실행·사업형": 1.0},
    "추진력": {"실행·사업형": 1.0},
    "관계지향성": {"관계·중재형": 1.0},
    "관계조화성": {"관계·중재형": 0.9},
    "영향력": {"관계·중재형": 0.8, "표현·창작형": 0.3},
    "공감성": {"관계·중재형": 0.9},
    "창의성": {"표현·창작형": 1.0},
    "언어 표현력": {"표현·창작형": 0.9},
    "감정 표현성": {"표현·창작형": 0.8},
    "신중성": {"관리·안정형": 0.8, "전략·참모형": 0.4},
    "안정지향성": {"관리·안정형": 1.0},
    "지속성": {"관리·안정형": 0.8, "실행·사업형": 0.2},
    "직관력": {"감지·직관형": 1.0},
    "감각 민감도": {"감지·직관형": 0.85},
    "상황 감지력": {"감지·직관형": 0.95},

    # UI 확장 본성 반영
    "능동성": {"실행·사업형": 0.75, "전략·참모형": 0.25},
    "경쟁성": {"실행·사업형": 0.70, "전략·참모형": 0.20},
    "표현력": {"표현·창작형": 0.90, "관계·중재형": 0.30},
    "이해력": {"관계·중재형": 0.80, "연구·분석형": 0.25},
    "자기표현성": {"관계·중재형": 0.45, "실행·사업형": 0.35, "표현·창작형": 0.25},
    "소통성": {"관계·중재형": 0.80, "표현·창작형": 0.30},
    "포용성": {"관계·중재형": 0.75, "관리·안정형": 0.25},
    "책임감": {"관리·안정형": 0.45, "실행·사업형": 0.45},
    "결단형": {"실행·사업형": 0.75, "전략·참모형": 0.25},
    "집중성": {"연구·분석형": 0.45, "관리·안정형": 0.35},

    "욕구강조성": {"실행·사업형": 0.25},
    "불안민감성": {"감지·직관형": 0.35},
    "자기중심성": {"실행·사업형": 0.15},
    "감정변동성": {"감지·직관형": 0.45},
    "스트레스민감성": {"감지·직관형": 0.35},
    "비교민감성": {"관계·중재형": 0.20},
}

# =========================================================
# 유사 계열 그룹 제한
# =========================================================

SIMILAR_NATURE_GROUPS = {
    "cognition_group": [
        "분석력",
        "논리성",
        "판단력",
        "탐구성",
        "분석성",
        "직관성",
    ],

    "relation_group": [
        "관계지향성",
        "공감성",
        "소통성",
        "이해력",
        "포용성",
    ],

    "execution_group": [
        "실행성",
        "추진력",
        "주도성",
        "능동성",
        "도전성",
    ],
}

GROUP_MAX_BONUS = {
    "cognition_group": 1.8,
    "relation_group": 1.6,
    "execution_group": 1.8,
}

# 같은 뜻/유사 입력명 정리
NATURE_ALIASES = {
    "변화지향": "변화지향성",
    "확장성": "확장형",
    "분석성": "분석력",
    "탐구성": "탐구성",
    "전략형": "전략성",
    "관계지향성": "관계지향",
    "고활력형": "고활력성",
    "고활력": "고활력성",
    "실행": "실행성",
    "리더십": "주도성",
    "회복탄력성": "회복 탄력성",
    "위험감수성": "위험 감수성",
    "감정변동": "감정 변동성",
    "결단력": "결단형",
    "지속성": "지속성",
    "집중력": "집중형",
    "자기관리성": "자기관리",
    "언어 이해/표현": "표현력",
    "분석형": "분석력",
    "탐구형": "탐구성",
    "판단형": "판단력",
    "창의형": "창의성",
    "직관형": "직관력",
    "욕구강조형": "욕구강조성",
    "긴장형": "불안민감성",
    "긴장민감형": "불안민감성",
    "자기중심형": "자기중심성",
    "감정변동형": "감정변동성",
    "스트레스 민감형": "스트레스민감성",
    "비교 민감형": "비교민감성",
    "저활력형": "저활력성",
    "변동성": "리듬안정성",
    "집중형": "집중성",
    "피로 민감성": "피로민감성",
    "스트레스 민감성": "스트레스민감성",
    "리듬 안정성": "리듬안정성",
}


CURRENT_JOB_ALIASES = {
    "연구": "연구·분석형",
    "분석": "연구·분석형",
    "기획": "전략·참모형",
    "전략": "전략·참모형",
    "사업": "실행·사업형",
    "영업": "실행·사업형",
    "운영": "관리·안정형",
    "행정": "관리·안정형",
    "관리": "관리·안정형",
    "상담": "관계·중재형",
    "교육": "관계·중재형",
    "hr": "관계·중재형",
    "콘텐츠": "표현·창작형",
    "디자인": "표현·창작형",
    "작가": "표현·창작형",
    "모니터링": "감지·직관형",
    "위기": "감지·직관형",
}

# =========================================================
# 2. 데이터 구조
# =========================================================

@dataclass
class RootState:
    stability: float
    drive: float
    cognition: float
    relation: float


# =========================================================
# 3. 입력 정규화
# =========================================================

def normalize_nature_names(natures: List[str]) -> List[str]:
    out: List[str] = []
    for item in natures:
        item = safe_text(item)
        if not item:
            continue
        out.append(NATURE_ALIASES.get(item, item))
    # 중복 제거, 순서 유지
    seen = set()
    dedup = []
    for x in out:
        if x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup

def form_get(obj, key, default=None):
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return default


def form_getlist(obj, key):
    """
    Flask ImmutableMultiDict / 일반 dict 둘 다 처리
    """
    if hasattr(obj, "getlist"):
        return obj.getlist(key)

    if isinstance(obj, dict):
        value = obj.get(key, [])
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    return []

def normalize_input_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    1) 이미 정리된 dict 입력
    2) Flask request.form(ImmutableMultiDict) 입력
    둘 다 처리
    """

    def _get(obj, key, default=None):
        if hasattr(obj, "get"):
            return obj.get(key, default)
        return default

    def _getlist(obj, key):
        if hasattr(obj, "getlist"):
            return obj.getlist(key)
        if isinstance(obj, dict):
            value = obj.get(key, [])
            if value is None:
                return []
            if isinstance(value, list):
                return value
            return [value]
        return []

    ESSENCE_CODE_MAP = {
        "adaptability": "적응성",
        "learning": "학습성",
        "relation": "관계성",
        "expression": "표현성",
        "drive": "추진성",
        "safety": "안전성",
        "reaction": "반응성",
    }

    NATURE_CODE_MAP = {
        # A 행동/추진
        "execution": "실행성",
        "challenge": "도전성",
        "drive": "추진력",
        "initiative": "주도성",
        "responsibility": "책임감",
        "active": "능동성",
        "competitive": "경쟁성",

        # B 인지/사고
        "analysis": "분석력",
        "inquiry": "탐구성",
        "judgment": "판단력",
        "creativity": "창의성",
        "logic": "논리성",
        "intuition": "직관력",

        # C 관계/사회
        "relation_oriented": "관계지향성",
        "relation_harmony": "관계조화성",
        "influence": "영향력",
        "empathy": "공감성",
        "communication": "소통성",
        "inclusion": "포용성",
        "expression": "표현력",
        "understanding": "이해력",
        "self_expression": "자기표현성",

        # D 안정/변화
        "stability": "안정지향성",
        "change": "변화지향성",
        "expansion": "확장성",
        "conservative": "보수성",
        "risk_avoidance": "위험회피성",

        # E 내부 상태
        "desire": "욕구강조성",
        "anxiety_sensitive": "불안민감성",
        "self_centered": "자기중심성",
        "emotion_fluctuation": "감정변동성",
        "stress_sensitive": "스트레스민감성",
        "comparison_sensitive": "비교민감성",

        # F 판단/결정
        "careful": "신중성",
        "intuition_decision": "직관성",
        "analysis_decision": "분석성",
        "avoidant": "회피성",
        "strategic": "전략성",
        "impulsive": "즉흥형",
        "decisive": "결단형",

        # G 활동성/활력
        "high_energy": "고활력성",
        "sustained": "지속성",
        "low_energy": "저활력성",
        "fluctuating": "활력변동성",
        "focus": "집중성",
        "fatigue_sensitive": "피로민감성",
        "stable_rhythm": "리듬안정성",
    }

    ENV_SCORE_MAP = {
        "very_poor": 20,
        "poor": 35,
        "trying": 50,
        "hopeful": 65,
        "ready": 80,
    }

    HEALTH_SCORE_MAP = {
        "strong": 80,
        "vital": 70,
        "normal": 55,
        "weak": 40,
        "ill": 25,
    }

    # -------------------------------------------------
    # 1. 이미 정리된 dict 입력이면 그대로 흡수
    # -------------------------------------------------
    if isinstance(raw, dict) and (
        "essences" in raw
        or "natures" in raw
        or "current_status" in raw
        or "execution" in raw
    ):
        essence_raw = get_first(raw, [
            "essences", "essence", "selected_essences", "core_essences", "origin_essences",
            "본질", "핵심 본질"
        ], [])
        natures_raw = get_first(raw, [
            "natures", "nature", "selected_natures", "current_natures", "traits",
            "본성", "현재 본성"
        ], [])

        experience_raw = get_first(raw, [
            "experience_patterns", "experience", "patterns", "경험", "경험 패턴"
        ], {})

        current_status_raw = get_first(raw, [
            "current_status", "status", "현재 상태"
        ], {})

        execution_raw = get_first(raw, [
            "execution", "execution_conditions", "reality_conditions", "실행", "실행 조건", "현실 조건"
        ], {})

        normalized = {
            "name": safe_text(get_first(raw, ["name", "이름"], "사용자"), "사용자"),
            "gender": safe_text(get_first(raw, ["gender", "성별"], "")),
            "age": safe_text(get_first(raw, ["age", "나이", "만나이"], "")),
            "current_job": safe_text(get_first(raw, ["current_job", "job", "직업", "현재 직업"], "")),
            "essences": flatten_selected(essence_raw),
            "natures": normalize_nature_names(flatten_selected(natures_raw)),
            "experience": experience_raw if isinstance(experience_raw, dict) else {},
            "current_status": current_status_raw if isinstance(current_status_raw, dict) else {},
            "execution": execution_raw if isinstance(execution_raw, dict) else {},
            "current_goals": get_first(raw, ["current_goals", "current_goal", "현재 목표"], []),
            "goal": get_first(raw, ["goal", "current_goal_1", "현재 목표"], ""),
            "concern": get_first(raw, ["concern", "current_goal_2", "현재 고민"], ""),

            # 호환용 유지
            "current_goal_1": get_first(raw, ["goal", "current_goal_1", "현재 목표"], ""),
            "current_goal_2": get_first(raw, ["concern", "current_goal_2", "현재 고민"], ""),
            "lang": safe_text(get_first(raw, ["lang", "language", "ui_lang"], "ko"), "ko"),
            "raw": raw,
        }

        return normalized

    # -------------------------------------------------
    # 2. Flask request.form 구조 처리
    # -------------------------------------------------
    essence_codes = _getlist(raw, "essence")
    essences = [ESSENCE_CODE_MAP.get(x, x) for x in essence_codes]

    nature_keys = [
        "nature_action",
        "nature_cognition",
        "nature_social",
        "nature_change",
        "nature_inner",
        "nature_decision",
        "nature_energy",
    ]

    natures = []
    for key in nature_keys:
        for val in _getlist(raw, key):
            natures.append(NATURE_CODE_MAP.get(val, val))

    environment_state = _get(raw, "environment_state", "")
    health_state = _get(raw, "health_state", "")

    env_score = ENV_SCORE_MAP.get(environment_state, 50)
    health_score = HEALTH_SCORE_MAP.get(health_state, 55)

    exp_results = _getlist(raw, "experience_result[]")
    exp_score = 50
    for r in exp_results:
        if r == "성공":
            exp_score += 10
        elif r == "안정":
            exp_score += 5
        elif r == "사퇴":
            exp_score -= 5
        elif r == "실패":
            exp_score -= 10
    exp_score = clamp(exp_score)
    goal_list = _getlist(raw, "current_goal")

    normalized = {
        "name": safe_text(_get(raw, "name", "사용자"), "사용자"),
        "gender": safe_text(_get(raw, "gender", "")),
        "age": "",
        "current_job": safe_text(_get(raw, "job", "")),
        "essences": essences,
        "natures": normalize_nature_names(natures),
        "experience": {
            "success": exp_score,
            "failure_recovery": 50,
            "consistency": 50,
            "trust": 50,
        },
        "current_status": {
            "health": health_score,
            "건강": health_score,
        },
        "execution": {
            "environment": env_score,
            "환경": env_score,
        },
        "current_goals": goal_list,
        "goal": (goal_list + [""])[0],
        "concern": (goal_list + ["", ""])[1],

        # 호환용 유지
        "current_goal_1": (goal_list + [""])[0],
        "current_goal_2": (goal_list + ["", ""])[1],
        "lang": safe_text(_get(raw, "lang", _get(raw, "language", _get(raw, "ui_lang", "ko"))), "ko"),
        "raw": raw,
    }

    return normalized


# =========================================================
# 4. 하위 상태(HW/SW/환경/경험) 계산
# =========================================================

def compute_hw_score(data: Dict[str, Any]) -> float:
    s = data.get("current_status", {})
    values = [
        normalize_score(get_first(s, ["health", "건강", "건강 상태"], 55)),
        normalize_score(get_first(s, ["energy", "활력", "활동성"], 55)),
        normalize_score(get_first(s, ["sleep", "수면"], 50)),
        normalize_score(get_first(s, ["emotion_stability", "정서 안정", "감정 안정"], 55)),
    ]
    return clamp(avg(values, 55))


def compute_sw_score(data: Dict[str, Any]) -> float:
    s = data.get("current_status", {})
    values = [
        normalize_score(get_first(s, ["focus", "집중성", "집중력"], 55)),
        normalize_score(get_first(s, ["thinking", "사고 정리", "생각 정리"], 55)),
        normalize_score(get_first(s, ["execution_power", "실행력", "추진력"], 55)),
        normalize_score(get_first(s, ["self_control", "자기조절", "자기관리"], 55)),
    ]
    return clamp(avg(values, 55))


def compute_environment_support(data: Dict[str, Any]) -> float:
    e = data.get("execution", {})
    values = [
        normalize_score(get_first(e, ["time", "시간 여건"], 50)),
        normalize_score(get_first(e, ["money", "경제 여건", "재정"], 50)),
        normalize_score(get_first(e, ["family_support", "가족 지원"], 50)),
        normalize_score(get_first(e, ["social_support", "사회 지원", "주변 지원"], 50)),
        normalize_score(get_first(e, ["opportunity", "기회", "환경 기회"], 50)),
    ]
    return clamp(avg(values, 50))


def compute_experience_score(data: Dict[str, Any]) -> float:
    ex = data.get("experience", {})
    values = [
        normalize_score(get_first(ex, ["success", "성공 경험"], 55)),
        normalize_score(get_first(ex, ["failure_recovery", "실패 회복", "회복 경험"], 50)),
        normalize_score(get_first(ex, ["consistency", "지속 경험", "반복 성과"], 50)),
        normalize_score(get_first(ex, ["trust", "자기 신뢰", "자신감"], 55)),
    ]
    return clamp(avg(values, 52))

def parse_experience(form):
    jobs = form.getlist("experience_job[]")
    results = form.getlist("experience_result[]")

    score = 50
    for r in results:
        if r == "성공":
            score += 10
        elif r == "실패":
            score -= 10

    return clamp(score)

# =========================================================
# 5. 본질-본성 정렬도
# =========================================================

def compute_essence_alignment(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    selected_essences = [e for e in data.get("essences", []) if e in ESSENCE_NATURE_MAP]
    selected_natures = data.get("natures", [])

    result: Dict[str, Dict[str, Any]] = {}

    for essence in selected_essences:
        mapping = ESSENCE_NATURE_MAP.get(essence, {})
        matched_details = []
        for nature in selected_natures:
            if nature in mapping:
                matched_details.append((nature, mapping[nature]))

        if mapping:
            matched_score = sum(weight for _, weight in matched_details)
            max_possible = sum(mapping.values())
            alignment = (matched_score / max_possible) * 100 if max_possible > 0 else 0
        else:
            alignment = 0

        result[essence] = {
            "alignment": clamp(alignment),
            "matched": sorted(matched_details, key=lambda x: x[1], reverse=True),
            "unmatched_count": max(0, len(mapping) - len(matched_details)),
        }

    return result


def classify_essence_expression(alignment: float, environment: float, selected_natures: List[str], essence: str) -> str:
    mapped = ESSENCE_NATURE_MAP.get(essence, {})
    over_expression = 0
    for n in selected_natures:
        if n not in mapped:
            continue
        if mapped[n] <= 0.45:
            over_expression += 1

    if alignment >= 60 and environment >= 60:
        return "자연스럽게 살아나는 형"
    if alignment >= 60 and environment < 60:
        return "버팀으로 드러나는 형"
    if alignment < 40 and len(selected_natures) >= 3:
        return "억제하는 형"
    if alignment < 50 and over_expression >= 2:
        return "과잉 스타일 형"
    return "행동과 억제의 혼합 형"

# =========================================================
# 5-1. 정렬도/충돌 해석 보강
# =========================================================

ESSENCE_NATURE_GROUP_MAP = {
    "적응성": {
        "primary": ["변화지향성", "확장형", "직관력", "고활력성", "활력변동성"],
        "support": ["탐구성", "도전성", "집중성"],
        "conflict": ["안정지향성", "위험회피성", "저활력성"],
    },
    "학습성": {
        "primary": ["분석력", "탐구성", "논리성", "판단력", "전략성"],
        "support": ["집중성", "신중성"],
        "conflict": ["회피성", "즉흥형", "감정 변동성"],
    },
    "관계성": {
        "primary": ["관계지향", "관계융화", "공감성", "소통성", "포용성", "영향력"],
        "support": ["이해력", "표현력", "포용성"],
        "conflict": ["자기중심성", "감정 변동성", "비교 민감성"],
    },
    "표현성": {
        "primary": ["표현력", "창의성", "영향력", "소통성", "자기주장", "고활력성"],
        "support": ["관계지향", "직관력"],
        "conflict": ["회피성", "저활력성", "자기중심성"],
    },
    "추진성": {
        "primary": ["실행성", "도전성", "추진력", "주도성", "책임감", "능동성", "경쟁성", "결단형"],
        "support": ["지속성", "집중성", "전략성"],
        "conflict": ["회피성", "저활력성", "안정지향성"],
    },
    "안전성": {
        "primary": ["안정지향성", "신중성", "지속성", "리듬안정성", "위험회피성"],
        "support": ["책임감", "자기관리"],
        "conflict": ["즉흥형", "변화지향성", "활력변동성"],
    },
    "반응성": {
        "primary": ["직관력", "활력변동성", "고활력성", "피로민감성", "스트레스민감성"],
        "support": ["공감성", "집중성"],
        "conflict": ["저활력성", "안정지향성"],
    },
    "남성성": {
        "primary": ["논리성", "실행성", "주도성", "능동성", "경쟁성", "결단형", "집중성"],
        "support": ["도전성", "분석력"],
        "conflict": ["회피성", "저활력성"],
    },
    "여성성": {
        "primary": ["공감성", "관계지향", "포용성", "표현력", "이해력"],
        "support": ["관계융화", "직관력"],
        "conflict": ["자기중심성", "경쟁성"],
    },
}


def get_alignment_label(score: float) -> str:
    if score >= 75:
        return "높음"
    if score >= 55:
        return "부분 정렬"
    if score >= 40:
        return "보완 필요"
    return "낮음"


def compute_alignment_overview(data: Dict[str, Any], alignment_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if not alignment_map:
        return {
            "average_alignment": 50.0,
            "label": "비교 정보 부족",
            "best_essence": None,
            "lowest_essence": None,
        }

    sorted_items = sorted(
        alignment_map.items(),
        key=lambda x: x[1].get("alignment", 50),
        reverse=True
    )
    avg_alignment = avg([v.get("alignment", 50) for _, v in sorted_items], 50)

    return {
        "average_alignment": round(avg_alignment, 1),
        "label": get_alignment_label(avg_alignment),
        "best_essence": {"name": sorted_items[0][0], "score": round(sorted_items[0][1].get("alignment", 50), 1)},
        "lowest_essence": {"name": sorted_items[-1][0], "score": round(sorted_items[-1][1].get("alignment", 50), 1)},
    }


def detect_essence_conflicts(data: Dict[str, Any], alignment_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    natures = data.get("natures", [])
    conflicts = []

    for essence in data.get("essences", []):
        rule = ESSENCE_NATURE_GROUP_MAP.get(essence)
        if not rule:
            continue

        matched_conflicts = [n for n in natures if n in rule.get("conflict", [])]
        matched_primary = [n for n in natures if n in rule.get("primary", [])]
        alignment = alignment_map.get(essence, {}).get("alignment", 50)

        if matched_conflicts and alignment < 55:
            if essence == "학습성":
                msg = "생각을 깊게 할 힘은 있으나, 실제 판단이나 실행 흐름이 흔들리면 분석력이 충분히 살아나지 못하게 될 수 있습니다."
            elif essence == "관계성":
                msg = "대인관계 능력은 있으나, 감정 기복이나 자기중심적 방어가 관계 흐름을 불안정하게 만들 수 있습니다."
            elif essence == "추진성":
                msg = "앞으로 밀고 나가려는 본성은 있으나, 활력이나 결정 흐름이 이를 끝까지 받쳐주지 못할 수 있습니다."
            elif essence == "안전성":
                msg = "안정을 지키려는 힘은 있으나, 변화 충동이나 즉흥성이 섞이면 안정 상태가 쉽게 흔들릴 수 있습니다."
            elif essence == "표현성":
                msg = "표현력은 있으나, 활력의 저하나 방어적 태도가 겹치면 강점이 밖으로 잘 표현되지 않을 수 있습니다."
            elif essence == "적응성":
                msg = "변화에 대응하는 능력은 있으나, 안정 고수나 활력 저하가 강해지면 적응력이 실제로 이어지기 어려울 수 있습니다."
            elif essence == "반응성":
                msg = "상황을 민감하게 읽는 힘은 있으나, 피로 누적이나 안정 고수 성향이 겹치면 반응성이 둔해질 수 있습니다."
            elif essence == "남성성":
                msg = "현 상황을 밀고 나가는 성향은 있으나, 회피나 활력 저하가 겹치면 남성의 강점이 자연스럽게 드러나기 어렵습니다."
            elif essence == "여성성":
                msg = "관계와 공감의 성향은 있으나, 방어적 태도가 강해지면 여성의 장점이 부드럽게 살아나지 못할 수 있습니다."
            else:
                msg = f"{essence} 본성은 있으나, 현재 본성 흐름과 일부 상충되어 강점이 충분히 드러나지 못할 수 있습니다."

            conflicts.append({
                "essence": essence,
                "alignment": round(alignment, 1),
                "conflict_traits": matched_conflicts[:3],
                "support_traits": matched_primary[:3],
                "message": msg,
            })

    return sorted(conflicts, key=lambda x: x["alignment"])

# =========================================================
# 6. Root 상태 계산
# =========================================================

def compute_root_state(data: Dict[str, Any], alignment_map: Dict[str, Dict[str, Any]]) -> RootState:
    hw = compute_hw_score(data)
    sw = compute_sw_score(data)
    env = compute_environment_support(data)
    exp = compute_experience_score(data)

    s = data.get("current_status", {})
    natures = data.get("natures", [])
    essences = data.get("essences", [])

    # 기본 상태값
    stability = 0.45 * hw + 0.20 * sw + 0.20 * env + 0.15 * exp
    drive = 0.25 * hw + 0.35 * sw + 0.20 * env + 0.20 * exp
    cognition = 0.20 * hw + 0.40 * sw + 0.15 * env + 0.25 * exp
    relation = 0.20 * hw + 0.20 * sw + 0.25 * env + 0.35 * exp

    # 현재 상태 입력 반영
    stability += 0.15 * normalize_score(get_first(s, ["emotional_balance", "정서 안정", "감정 안정"], 50)) - 7.5
    drive += 0.15 * normalize_score(get_first(s, ["motivation", "동기", "의욕"], 50)) - 7.5
    cognition += 0.15 * normalize_score(get_first(s, ["clarity", "판단 명료성", "생각 명료성"], 50)) - 7.5
    relation += 0.15 * normalize_score(get_first(s, ["relationship_state", "대인 관계 상태", "관계 상태"], 50)) - 7.5

    # 본질 Root 보정
    for essence in essences:
        alignment = alignment_map.get(essence, {}).get("alignment", 50)
        bonus_map = ESSENCE_ROOT_BONUS.get(essence, {})
        for root_key, bonus in bonus_map.items():
            scaled = bonus * ((alignment - 50) / 50.0)
            if root_key == "stability":
                stability += scaled
            elif root_key == "drive":
                drive += scaled
            elif root_key == "cognition":
                cognition += scaled
            elif root_key == "relation":
                relation += scaled

    # 특정 본성 직접 보정
    nature_adjust = {
        "분석력": (0, 0, 6, 0),
        "탐구성": (0, 0, 5, 0),
        "전략성": (0, 1, 6, 0),
        "판단력": (0, 0, 4, 0),
        "관계지향": (0, 0, 0, 6),
        "관계융화": (1, 0, 0, 5),
        "공감성": (0, 0, 0, 5),
        "창의성": (0, 1, 3, 1),
        "주도성": (0, 6, 0, 0),
        "도전성": (0, 5, 0, 0),
        "실행성": (0, 6, 0, 0),
        "지속성": (4, 2, 0, 0),
        "신중성": (4, -1, 1, 0),
        "직관력": (0, 0, 2, 1),
        "능동성": (0, 5, 1, 0),
        "경쟁성": (-1, 5, 0, 0),
        "책임감": (3, 3, 0, 0),
        "결단형": (0, 5, 1, 0),
        "소통성": (0, 0, 1, 4),
        "포용성": (2, 0, 0, 4),
        "표현력": (0, 1, 2, 3),
        "이해력": (1, 0, 3, 3),
        "자기주장": (-1, 3, 1, 1),
        "고활력성": (0, 4, 0, 0),
        "저활력성": (-2, -5, 0, 0),
        "리듬안정형": (4, 1, 0, 0),
        "피로민감성": (-3, -2, 0, 0),
        "스트레스민감성": (-4, -1, -1, 0),
        "감정변동성": (-4, -1, -1, 1),
        "감정민감성": (-2, 0, 0, 2),
        "불안민감성": (-5, -1, -1, -1),
    }
    for nature in natures:
        if nature in nature_adjust:
            ds, dd, dc, dr = nature_adjust[nature]
            stability += ds
            drive += dd
            cognition += dc
            relation += dr

    return RootState(
        stability=clamp(stability),
        drive=clamp(drive),
        cognition=clamp(cognition),
        relation=clamp(relation),
    )

# =========================================================
# 7. 위협 / 기회 벡터
# =========================================================

def compute_threat_vectors(data: Dict[str, Any], root: RootState, alignment_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    위협 벡터는 '부족/부담'만 담는다.
    낮은 본질 정렬도는 기회 벡터와 중복되지 않도록 여기에서만 다룬다.
    """
    threats: List[Dict[str, Any]] = []
    env = compute_environment_support(data)

    if root.stability < 50:
        threats.append({
            "factor": "건강·정서 안정 보완",
            "score": round(100 - root.stability, 1),
            "rationale": "신체 상태나 정서 안정이 흔들리면 전체 판단과 실행 흐름이 약해질 수 있습니다.",
        })
    if root.drive < 50:
        threats.append({
            "factor": "실행 연결 부족",
            "score": round(100 - root.drive, 1),
            "rationale": "방향을 알고 있어도 실제 행동으로 이어지는 힘이 약해질 수 있습니다.",
        })
    if root.cognition < 50:
        threats.append({
            "factor": "생각 정리·판단 혼선",
            "score": round(100 - root.cognition, 1),
            "rationale": "우선순위 정리와 판단 흐름에 혼선이 생길 수 있습니다.",
        })
    if root.relation < 50:
        threats.append({
            "factor": "관계 부담",
            "score": round(100 - root.relation, 1),
            "rationale": "관계의 부담이나 연결 부족이 전체 흐름을 약하게 만들 수 있습니다.",
        })
    if env < 50:
        threats.append({
            "factor": "현실 여건 압박",
            "score": round(100 - env, 1),
            "rationale": "시간·경제·환경 지원이 약하면 준비가 있어도 변화 속도가 늦어질 수 있습니다.",
        })

    for essence, info in alignment_map.items():
        a = info.get("alignment", 50)
        if a < 45:
            threats.append({
                "factor": f"{essence} 실천 연결 부족",
                "score": round(100 - a, 1),
                "rationale": f"'{essence}' 성향은 있으나, 현재 본성 선택과의 연결이 약해 실제 행동이나 결과로 이어지는 힘이 부족해보입니다.",
            })

    return sorted(threats, key=lambda x: x["score"], reverse=True)[:5]

def compute_opportunity_vectors(data: Dict[str, Any], root: RootState, alignment_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    기회 벡터는 '현재 활용 가능한 자원/강점'만 담는다.
    낮은 정렬도는 위협 벡터에서만 다루어 그래프와 문장 중복을 줄인다.
    """
    opps: List[Dict[str, Any]] = []
    env = compute_environment_support(data)
    exp = compute_experience_score(data)

    if root.stability >= 55:
        opps.append({"factor": "건강·안정 기반", "score": round(root.stability, 1), "rationale": "기반을 유지하며 다음 선택을 준비할 수 있는 안정 축이 있습니다."})
    if root.drive >= 55:
        opps.append({"factor": "실행 추진 자원", "score": round(root.drive, 1), "rationale": "생각을 실제 행동으로 연결할 수 있는 추진 상태가 있습니다."})
    if root.cognition >= 55:
        opps.append({"factor": "사고·판단 자원", "score": round(root.cognition, 1), "rationale": "생각을 정리하고 방향을 설계하는 힘이 비교적 살아 있습니다."})
    if root.relation >= 55:
        opps.append({"factor": "관계·연결 자원", "score": round(root.relation, 1), "rationale": "사람과 연결되며 조정하고 협력할 수 있는 힘이 있습니다."})
    if env >= 60:
        opps.append({"factor": "환경 지원", "score": round(env, 1), "rationale": "현실 여건이 비교적 받쳐주어 본성이 실제 행동으로 이어지기 유리합니다."})
    if exp >= 60:
        opps.append({"factor": "경험 축적", "score": round(exp, 1), "rationale": "축적된 경험이 현재 선택의 신뢰도를 높여줍니다."})

    for essence, info in alignment_map.items():
        a = info.get("alignment", 50)
        if a >= 60:
            opps.append({
                "factor": f"{essence} 활용 강점",
                "score": round(a, 1),
                "rationale": f"핵심 본질인 '{essence}'이 현재 본성 흐름과 비교적 잘 연결되어 강점으로 작용할 수 있습니다.",
            })

    return sorted(opps, key=lambda x: x["score"], reverse=True)[:5]

# =========================================================
# 8. 미래 흐름 계산
# =========================================================

def compute_future_potential(root: RootState, environment: float, alignment_map: Dict[str, Dict[str, Any]]) -> float:
    root_avg = avg([root.stability, root.drive, root.cognition, root.relation], 50)
    core_essences = sorted(alignment_map.items(), key=lambda x: x[1].get("alignment", 50))[:3]
    mismatch = avg([100 - item[1].get("alignment", 50) for item in core_essences], 45)
    potential = 0.5 * root_avg + 0.3 * environment - 0.2 * mismatch + 25
    return clamp(potential)


def build_path_distribution(root: RootState, environment: float, alignment_map: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    사용자에게는 3분류만 보여준다.
    개선/완만 개선, 위협/완만 위협의 중복 인상을 줄이기 위한 출력 구조.
    """
    potential = compute_future_potential(root, environment, alignment_map)
    root_avg = avg([root.stability, root.drive, root.cognition, root.relation], 50)
    mismatch = avg([100 - x.get("alignment", 50) for x in alignment_map.values()], 40) if alignment_map else 40

    improvement = clamp(
        0.40 * potential +
        0.20 * root.drive +
        0.15 * root.cognition +
        0.15 * environment -
        0.10 * mismatch
    )
    maintenance = clamp(
        0.45 * root_avg +
        0.25 * root.stability +
        0.15 * environment -
        0.05 * mismatch
    )
    threat = clamp(
        0.35 * (100 - root.stability) +
        0.25 * (100 - environment) +
        0.20 * mismatch +
        0.20 * (100 - root.drive)
    )

    raw = {
        "개선 흐름": improvement,
        "유지 흐름": maintenance,
        "위협 흐름": threat,
    }

    total = sum(raw.values()) or 1.0
    normalized = {k: round(v / total * 100, 1) for k, v in raw.items()}

    diff = round(100.0 - sum(normalized.values()), 1)
    if diff != 0:
        key = max(normalized, key=normalized.get)
        normalized[key] = round(normalized[key] + diff, 1)

    return normalized

def evaluate_path_decision(path_distribution: Dict[str, float]) -> Dict[str, Any]:
    ranked = sorted(path_distribution.items(), key=lambda x: x[1], reverse=True)
    first_name, first_score = ranked[0]
    second_name, second_score = ranked[1] if len(ranked) > 1 else ("", 0)

    improvement = path_distribution.get("개선 흐름", 0)
    maintenance = path_distribution.get("유지 흐름", 0)
    threat = path_distribution.get("위협 흐름", 0)

    if first_name == "개선 흐름" and improvement >= 40 and improvement >= threat + 5:
        final = "개선 중심"
    elif first_name == "위협 흐름" and threat >= 40 and threat >= improvement + 5:
        final = "위협 관리"
    elif first_name == "유지 흐름" and maintenance >= 34:
        final = "유지 중심"
    else:
        final = "혼합 상태"

    return {
        "final_decision": final,
        "top_path": {"name": first_name, "score": first_score},
        "second_path": {"name": second_name, "score": second_score},
    }

def explain_single_path(path_name: str) -> str:
    explanations = {
        "개선 흐름": "현재 자원을 조금씩 실제 행동으로 연결하면 상태가 나아질 가능성이 있습니다.",
        "유지 흐름": "무리한 확장보다 현재 기반을 안정적으로 지키며 균형을 맞추는 편이 유리합니다.",
        "위협 흐름": "성장보다 먼저 부담 요인을 줄이고 약한 부분을 보완하는 것이 중요합니다.",
        "개선 경로": "현재 자원을 조금씩 실제 행동으로 연결하면 상태가 나아질 가능성이 있습니다.",
        "완만 개선": "작은 개선을 누적시키는 방식이 현실적입니다.",
        "유지 경로": "무리한 확장보다 현재 기반을 안정적으로 지키는 편이 유리합니다.",
        "완만 위협": "피로와 부담이 서서히 누적되지 않도록 조정이 필요합니다.",
        "위협 경로": "성장보다 먼저 부담 요인을 줄이고 약한 부분을 보완하는 것이 중요합니다.",
    }
    return explanations.get(path_name, "현재 흐름을 종합적으로 검토할 필요가 있습니다.")

def build_path_explanations(path_distribution: Dict[str, float]) -> Dict[str, Any]:
    ranked = sorted(path_distribution.items(), key=lambda x: x[1], reverse=True)
    first = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ("", 0)
    others = ranked[2:3]

    return {
        "top1": {"name": first[0], "score": first[1], "text": explain_single_path(first[0])},
        "top2": {"name": second[0], "score": second[1], "text": explain_single_path(second[0])},
        "supplemental": [
            {"name": n, "score": s, "text": explain_single_path(n)} for n, s in others
        ],
    }

# =========================================================
# 9. 재능/직업 적합도 계산
# =========================================================

def compute_talent_axis_scores(data: Dict[str, Any], root: RootState, alignment_map: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    scores = {axis: 0.0 for axis in TALENT_AXES}

    # 1단계: 본질 -> 지능 축 1차 매핑
    for essence in data.get("essences", []):
        alignment = alignment_map.get(essence, {}).get("alignment", 50) / 100.0
        for axis, weight in ESSENCE_TALENT_MAP.get(essence, {}).items():
            scores[axis] += 45 * weight * alignment

    # 2단계: 본성 -> 발현 방식 보정
    # 유사 인지 계열은 중복 가산을 완화한다.
    selected_natures = data.get("natures", [])
    cognition_like = {
        "분석력",
        "분석성",
        "논리성",
        "판단력",
        "탐구성",
        "전략성",
    }

    cognition_seen = 0

    for nature in selected_natures:
        boost_map = NATURE_TALENT_BOOST.get(nature, {})

        for axis, weight in boost_map.items():
            multiplier = 1.0

            if nature in cognition_like and axis in ["연구·분석형", "전략·참모형"]:
                cognition_seen += 1

                if cognition_seen == 1:
                    multiplier = 1.0
                elif cognition_seen == 2:
                    multiplier = 0.55
                else:
                    multiplier = 0.30

            scores[axis] += 18 * weight * multiplier

    # 3단계: 현재 상태 / 경험 보정
    hw = compute_hw_score(data)
    sw = compute_sw_score(data)
    env = compute_environment_support(data)
    exp = compute_experience_score(data)

    scores["연구·분석형"] += 0.22 * root.cognition + 0.08 * sw + 0.05 * exp
    scores["전략·참모형"] += 0.18 * root.cognition + 0.10 * env + 0.06 * root.stability
    scores["실행·사업형"] += 0.24 * root.drive + 0.10 * env + 0.05 * hw
    scores["관계·중재형"] += 0.24 * root.relation + 0.07 * env + 0.04 * exp
    scores["표현·창작형"] += 0.14 * root.cognition + 0.10 * root.relation + 0.04 * sw
    scores["관리·안정형"] += 0.24 * root.stability + 0.08 * env + 0.05 * exp
    scores["감지·직관형"] += 0.12 * root.cognition + 0.10 * root.relation + 0.08 * hw

    # 건강/환경/경험이 낮으면 현실 발현도 감산
    realization = avg([hw, sw, env, exp], 52)
    penalty_factor = 0.85 if realization < 45 else (0.93 if realization < 55 else 1.0)
    for axis in scores:
        scores[axis] = clamp(scores[axis] * penalty_factor)

    return {k: round(v, 1) for k, v in scores.items()}


def infer_current_job_axis(current_job: str) -> str:
    text = current_job.strip().lower()
    if not text:
        return ""
    for key, axis in CURRENT_JOB_ALIASES.items():
        if key in text:
            return axis
    return ""

def classify_job_context(current_job: str) -> str:
    current_job = safe_text(current_job)

    if current_job == "학생":
        return "student"
    if current_job in ["은퇴/전환기", "무직/기타"]:
        return "transition"
    if current_job in ["프리랜서", "일용직/알바"]:
        return "flexible"
    return "regular"

def evaluate_current_job_fit(current_job: str, talent_scores: Dict[str, float]) -> Dict[str, Any]:
    current_job = safe_text(current_job)

    if current_job == "학생":
        return {
            "current_job_axis": "",
            "fit_label": "진로 탐색 단계",
            "fit_score": None,
            "job_context": "student",
            "reason": "현재는 직업 적합도보다, 앞으로 어떤 진로 방향이 적성에 맞는지를 찾는 것이 중요합니다.",
        }

    if current_job in ["은퇴/전환기", "무직/기타"]:
        return {
            "current_job_axis": "",
            "fit_label": "전환기 상태",
            "fit_score": None,
            "job_context": "transition",
            "reason": "현재는 특정 직업의 적합도보다, 다음 삶의 활동 방향과 구조가 본질과 본성에 맞는지를 보는 것이 중요합니다.",
        }

    if current_job in ["프리랜서", "일용직/알바"]:
        return {
            "current_job_axis": "",
            "fit_label": "유동적 직업 상태",
            "fit_score": None,
            "job_context": "flexible",
            "reason": "현재는 직업이 고정된 상태라기보다, 본성에 맞는 일의 방식과 방향을 탐색하는 과정으로 볼 수 있습니다.",
        }

    inferred = infer_current_job_axis(current_job)
    if not current_job or not inferred:
        return {
            "current_job_axis": inferred,
            "fit_label": "비교 정보 부족",
            "fit_score": None,
            "job_context": "unknown",
            "reason": "현재 직업 정보가 충분하지 않아 본성에 적합한 결과를 단정하기 어렵습니다.",
        }

    score = talent_scores.get(inferred, 50)
    if score >= 75:
        label = "잘 맞음"
        reason = "현재 역할이 대상자의 본성 강점과 비교적 잘 맞는 편입니다. 지금은 강점을 더 안정적으로 살리는 방향이 유리합니다."
    elif score >= 55:
        label = "부분적으로 맞음"
        reason = "현재 역할 안에 맞는 부분도 있지만, 강점이 충분히 살아나지 못하는 요소도 함께 섞여 있습니다."
    else:
        label = "현 본성과 맞지 않는 상태"
        reason = "현재 역할은 대상자의 핵심 재능 축을 충분히 살리기 어려운 상황일 가능성이 있습니다."

    return {
        "current_job_axis": inferred,
        "fit_label": label,
        "fit_score": round(score, 1),
        "job_context": "regular",
        "reason": reason,
    }


# =========================================================
# 10. 서술 생성
# =========================================================

def build_one_line_summary(name: str, root: RootState, final_decision: str) -> str:
    overall = avg([root.stability, root.drive, root.cognition, root.relation], 50)
    label = score_to_label(overall)

    if final_decision == "개선 중심":
        return f"현재는 '{label}' 수준으로, 약한 부분을 조금씩 보완하면 개선 흐름을 만들 가능성이 있습니다."
    if final_decision == "유지 중심":
        return f"현재는 '{label}' 수준으로, 무리한 확장보다 현재 기반을 안정적으로 유지하는 편이 더 적절합니다."
    if final_decision == "위협 관리":
        return f"현재는 '{label}' 수준으로, 성장보다 먼저 부담 요인을 줄이고 약한 부분을 보완하는 것이 중요합니다."
    return f"현재는 '{label}' 수준으로, 유지·개선·위협 요소가 함께 섞여 있어 선택에 따라 흐름이 달라질 수 있습니다."

def build_current_status_text(name: str, data: Dict[str, Any], root: RootState, opportunity_vectors: List[Dict[str, Any]]) -> str:
    overall = avg([root.stability, root.drive, root.cognition, root.relation], 50)
    overall_label = score_to_label(overall)

    lines = [
        f"{name}님의 현재는 전반적으로 {overall_label} 상태입니다.",
        f"신체 건강은 {score_to_label(root.stability)} 수준({root.stability:.1f}%), 실행 흐름은 {score_to_label(root.drive)} 수준({root.drive:.1f}%)입니다.",
        f"사고·판단 흐름은 {score_to_label(root.cognition)} 수준({root.cognition:.1f}%), 관계 흐름은 {score_to_label(root.relation)} 수준({root.relation:.1f}%)입니다.",
    ]

    env = compute_environment_support(data)

    if env >= 65:
        lines.append("환경 조건이 비교적 받쳐주고 있어 내부 자원이 실제 행동으로 이어질 가능성이 있습니다.")
    elif env < 50:
        lines.append("다만 환경 조건이 충분하지 않아 실행 흐름이 실제 변화로 이어지는 속도는 다소 제한될 수 있습니다.")

    job = data.get("current_job", "")

    if job == "학생":
        lines.append("현재는 직업 적합도보다 진로 방향을 설정하는 시기로 보는 것이 더 적절합니다.")
    elif job in ["은퇴/전환기", "무직/기타"]:
        lines.append("현재는 직업 유지보다 삶의 방향과 구조를 재정리하는 시기로 볼 수 있습니다.")
    elif job in ["프리랜서", "일용직/알바"]:
        lines.append("현재는 직업이 고정된 상태라기보다 방향을 탐색하는 과정으로 볼 수 있습니다.")

    if opportunity_vectors:
        top = opportunity_vectors[0]["factor"]
        lines.append(f"현재 상대적으로 근본의 강한 성향은 '{top}'입니다.")

    return " ".join(lines)

def build_core_problem_text(input_data, result):
    lines = []

    natures = input_data.get("natures", [])
    root_state = result.get("root_state", {}) or {}
    vitality = root_state.get("drive", 60)
    stability = root_state.get("stability", 60)
    cognition = root_state.get("cognition", 60)
    relation = root_state.get("relation", 60)

    has_avoid = "회피성" in natures
    has_tension = "불안민감성" in natures
    has_emotional_fluctuation = ("활력변동성" in natures) or ("감정변동성" in natures)
    low_vital = vitality < 55

    goal = input_data.get("current_goal_1")
    concern = input_data.get("current_goal_2")

    # 1. 목표와 부담의 관계를 '문제'가 아니라 '흐름'으로 해석
    if goal and concern:
        relation_map = {
            ("economic_stability", "health_recovery"): "경제적 안정으로 향하는 흐름과 건강 회복의 부담이 함께 작용하고 있습니다. 건강 기반이 약해지면 실행 속도가 제한될 수 있으므로, 회복과 안정의 순서를 먼저 잡는 편이 유리합니다.",
            ("performance_jump", "life_margin"): "성과를 높이려는 흐름과 삶의 여유를 확보하려는 흐름이 함께 작용하고 있습니다. 추진만 커지면 지속성이 약해질 수 있으므로, 성과와 회복의 균형이 중요합니다.",
            ("new_job", "economic_stability"): "새로운 직업을 탐색하려는 흐름과 경제적 안정을 지키려는 흐름이 함께 작용하고 있습니다. 변화 욕구와 안정 욕구의 균형에 따라 선택 방향이 달라질 수 있습니다.",
            ("relationship_improvement", "personality_change"): "관계를 개선하려는 흐름과 자기 변화에 대한 부담이 함께 작용하고 있습니다. 관계 변화는 상대보다 먼저 자신의 반응 방식이 정리될 때 안정적으로 이어질 수 있습니다.",
            ("family_peace", "relationship_improvement"): "가정의 평화를 원하는 흐름과 관계 개선의 부담이 함께 작용하고 있습니다. 관계 긴장을 먼저 낮출수록 전체 생활 흐름이 안정되기 쉽습니다.",
            ("health_recovery", "performance_jump"): "건강 회복의 필요와 성과 도약의 욕구가 함께 작용하고 있습니다. 지금은 무리한 추진보다 회복과 실행 속도의 균형을 잡는 것이 중요합니다.",
            ("life_margin", "economic_stability"): "삶의 여유를 원하는 흐름과 경제적 안정에 대한 부담이 함께 작용하고 있습니다. 경제 압박이 커지면 여유의 흐름이 제한될 수 있으므로 우선순위 정리가 필요합니다.",
            ("social_contribution", "social_recognition"): "사회에 기여하려는 흐름과 인정받고 싶은 흐름이 함께 작용하고 있습니다. 인정 욕구가 커지면 기여의 방향이 흔들릴 수 있으므로 목적을 먼저 정리하는 것이 좋습니다.",
        }
        relation_text = relation_map.get((goal, concern))
        if relation_text:
            lines.append(relation_text)
        else:
            goal_label = GOAL_CODE_MAP.get(goal, goal)
            concern_label = GOAL_CODE_MAP.get(concern, concern)
            lines.append(
                f"현재는 '{goal_label}'으로 향하는 흐름과 '{concern_label}'에 대한 부담이 함께 작용하고 있습니다. "
                "두 흐름의 우선순위가 정리될수록 실행 활력이 덜 분산됩니다."
            )

    # 2. 핵심 흐름: 감정 변동성은 여기에서 한 번만 구조적으로 설명
    if has_emotional_fluctuation or has_tension:
        lines.append(
            "현재 핵심 흐름은 감정 변화의 기복이 판단과 실행에 영향을 주는 구조입니다. "
            "감정 억제가 어려워지면, 판단과 실행 일관성이 흔들릴 수 있지만, "
            "동시에 상황 변화를 민감하게 읽는 기능으로도 작용할 수 있습니다. "
            "따라서 이 성향은 억누르기보다 중요한 결정 전에 정리 시간을 두고 방향을 설정해가는 편이 좋습니다."
        )
    elif has_avoid or low_vital:
        lines.append(
            "현재 핵심 흐름은 실행으로 이어지는 연결이 약해지는 구조입니다. "
            "방향은 존재하지만, 회피 성향이나 활력 저하가 겹치면 행동으로 이어지는 과정이 끊어지게 될 수 있습니다. "
            "지금은 무리하게 확장하기보다 실행 리듬을 안정시키는 접근이 필요합니다."
        )
    else:
        threats = result.get("threat_vectors", [])
        if threats:
            top = threats[0]
            lines.append(
                f"현재 흐름에서 가장 먼저 살펴볼 요소는 ‘{top.get('factor', '핵심 요소')}’입니다. "
                f"{top.get('rationale', '이 요소가 전체 흐름에 부담으로 작용하고 있습니다.')}"
            )
        else:
            weak_parts = []
            if stability < 55:
                weak_parts.append("건강·정서 안정")
            if vitality < 55:
                weak_parts.append("실행 흐름")
            if cognition < 55:
                weak_parts.append("생각 정리와 판단")
            if relation < 55:
                weak_parts.append("관계 흐름")
            if weak_parts:
                lines.append(f"현재는 {', '.join(weak_parts)} 부분을 보완하면 전체 흐름이 더 안정될 수 있습니다.")
            else:
                lines.append("현재는 특정 결함보다 강점이 실제 실행 흐름으로 자연스럽게 이어지도록 조정하는 것이 중요합니다.")

    # 3. 생애 단계 문장 보존
    age = input_data.get("age")
    try:
        age_int = int(age) if age not in (None, "") else None
    except Exception:
        age_int = None

    if age_int is not None:
        if age_int < 30:
            lines.append("현재는 성장기로, 다양한 경험을 통해 방향을 넓게 탐색하는 것이 중요합니다.")
        elif age_int < 50:
            lines.append("현재는 청년기로, 선택한 방향을 실제 성과로 연결하는 것이 중요한 시기입니다.")
        elif age_int < 70:
            lines.append("현재는 장년기로, 무리한 확장보다 강점을 현실 성과로 조정하는 편이 중요합니다.")
        else:
            lines.append("현재는 노년기로, 확장보다 삶의 안정과 질을 중요시하는 흐름으로 가는 것이 좋습니다.")

    return "\n".join(lines)


def build_future_flow_text(path_decision: Dict[str, Any], path_explanations: Dict[str, Any]) -> str:
    final_decision = path_decision["final_decision"]
    top1 = path_explanations["top1"]
    top2 = path_explanations["top2"]
    supplements = path_explanations.get("supplemental", [])

    lines = [f"최종 판정은 [{final_decision}]입니다."]

    if final_decision == "개선 중심":
        lines.append("현재는 보완할 부분이 있지만, 실행 방향을 작게 잡아 꾸준히 연결하면 개선 가능성이 살아나는 흐름입니다.")
    elif final_decision == "위협 관리":
        lines.append("현재는 확장보다 부담 요인을 먼저 줄이고, 건강·감정·실행 리듬을 안정시키는 것이 더 중요한 흐름입니다.")
    elif final_decision == "유지 중심":
        lines.append("현재는 큰 변화보다 기반을 유지하면서 필요한 부분만 조정하는 것이 더 유리한 흐름입니다.")
    else:
        lines.append("현재는 개선·유지·위협 요소가 함께 섞여 있어, 본성 변화와 환경 조건에 따라 흐름이 달라질 수 있습니다.")

    lines.extend([
        f"1순위 흐름은 {top1['name']}({top1['score']:.1f}%)이며, {top1['text']}",
        f"2순위 흐름은 {top2['name']}({top2['score']:.1f}%)이며, {top2['text']}",
    ])

    if supplements:
        extra = " / ".join([f"{x['name']}({x['score']:.1f}%): {x['text']}" for x in supplements[:1]])
        lines.append(f"보조 흐름 참고 – {extra}")

    return " ".join(lines)

def build_talent_analysis_text(talent_scores: Dict[str, float]) -> str:
    top_axes = top_n_items(talent_scores, 3)
    if not top_axes:
        return "현재 입력 기준으로 재능 축을 충분히 분류하지 못했습니다."

    parts = [f"{name}({score:.1f})" for name, score in top_axes]
    return f"현재 흐름을 종합하면 주요 지능·재능 본성은 {', '.join(parts)} 순으로 나타납니다. 이는 타고난 본질과 현재 나타나는 본성, 그리고 현실 조건을 함께 반영한 결과입니다."


def build_current_fit_text(current_fit: Dict[str, Any]) -> str:
    fit_label = current_fit.get("fit_label", "비교 정보 부족")
    job_context = current_fit.get("job_context", "")

    if job_context in ["student", "transition", "flexible"]:
        return f"{fit_label}로 해석됩니다. {current_fit.get('reason', '')}"

    if fit_label == "비교 정보 부족":
        return current_fit.get("reason", "현재 직업 정보가 부족합니다.")

    axis = current_fit.get("current_job_axis", "")
    score = current_fit.get("fit_score")

    if fit_label == "잘 맞음":
        tail = "현재 환경이 강한 흐름과 비교적 잘 맞아, 장점을 안정적으로 살리기 좋은 편입니다."
    elif fit_label == "부분적으로 맞음":
        tail = "현재 역할 안에 맞는 부분도 있지만, 강점이 실제로 충분히 드러나지 않는 요소도 함께 있습니다."
    else:
        tail = "현재 본성은 핵심 강점 축을 충분히 살리기 어려운 상태일 가능성이 있습니다."

    return f"현재 직업 상태를 '{axis}' 축으로 보았을 때, 적합도는 {fit_label}({score:.1f})으로 해석됩니다. {tail}"


def build_recommended_jobs_text(
    talent_scores: Dict[str, float],
    input_data: Dict[str, Any] | None = None
) -> str:
    input_data = input_data or {}

    name = safe_text(input_data.get("name")) or "이 분"

    age = input_data.get("age")
    try:
        age_int = int(age)
    except Exception:
        age_int = None

    if age_int is None:
        raw = input_data.get("raw")
        try:
            birth_year = int(raw.get("birth_year")) if raw else None
            from datetime import date
            age_int = date.today().year - birth_year if birth_year else None
        except Exception:
            age_int = None

    if age_int is None:
        life_stage = ""
    elif age_int < 30:
        life_stage = "성장기"
    elif age_int < 50:
        life_stage = "청년기"
    elif age_int < 70:
        life_stage = "장년기"
    else:
        life_stage = "노년기"

    recommend_count = 1 if life_stage == "노년기" else 3
    top_axes = top_n_items(talent_scores, recommend_count)

    lines = []

    current_job = safe_text(input_data.get("current_job") or input_data.get("job"))

    if current_job == "학생":
        lines.append("현재는 다양한 경험을 통해 방향을 탐색해가는 중요한 시기입니다.")
    if current_job in ["은퇴/전환기", "무직/기타"]:
        lines.append("현재는 직업 전환이나 재취업 여부보다, 삶의 리듬과 강점이 맞는 방향을 추구하는 것이 더 중요합니다.")
    elif current_job in ["프리랜서", "일용직/알바"]:
        lines.append("현재는 고정 직업보다 일의 방향이 유동적인 상태이므로, 아래 추천 축을 참고해 지속 가능한 활동 영역을 찾는 것이 좋습니다.")

    for axis, score in top_axes:
        jobs = JOB_GROUPS[axis]["jobs"][:5]
        caution = JOB_GROUPS[axis]["caution"]
        lines.append(
            f"- {axis} ({score:.1f}) → 추천 직업군: {', '.join(jobs)} / 주의 방향: {caution}"
        )

    if life_stage == "성장기":
        lines.append("")
        lines.append(f"{name}님은 성장기로, 위 추천 직업군 3개를 넓게 탐색하며 경험과 기초 역량을 쌓는 것이 좋습니다.")
    elif life_stage == "청년기":
        lines.append("")
        lines.append(f"{name}님은 청년기로, 위 추천 직업군 3개 중 현실 조건과 성과 가능성이 높은 방향을 중심으로 숙고하는 것이 좋습니다.")
    elif life_stage == "장년기":
        lines.append("")
        lines.append(f"{name}님은 장년기로, 위 추천 직업군 3개 중 지금까지의 경험과 강점을 가장 잘 살릴 수 있는 방향으로 검토하는 것이 좋습니다.")
    elif life_stage == "노년기":
        lines.append("")
        lines.append(f"{name}님은 노년기로, 직업군은 가장 부담이 적은 1개 방향만 참고하고, 건강·관계·삶의 질을 우선하는 선택이 더 적절합니다.")

    return "\n".join(lines)


def build_alignment_summary(data: Dict[str, Any], alignment_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    env = compute_environment_support(data)
    selected_natures = data.get("natures", [])
    summary = []
    for essence, info in alignment_map.items():
        alignment = info.get("alignment", 50)
        summary.append({
            "essence": essence,
            "alignment": round(alignment, 1),
            "expression_type": classify_essence_expression(alignment, env, selected_natures, essence),
            "matched": [x[0] for x in info.get("matched", [])[:4]],
        })
    return sorted(summary, key=lambda x: x["alignment"], reverse=True)


def build_nature_change_text(input_data: Dict[str, Any], result: Dict[str, Any]) -> str:
    """
    필요한 행동 조정 방향.
    기존 파일에는 build_action_guidance()가 없으므로 새 함수명에 의존하지 않고,
    결과 필드 nature_change_text를 직접 생성한다.
    감정 변동성 설명은 core_problem_text와 중복되지 않도록 행동 제안 중심으로만 정리한다.
    """
    natures = input_data.get("natures", []) or []
    lines: List[str] = []

    if "활력변동성" in natures or "감정변동성" in natures:
        lines.append(
            "감정 변동성이 있을 때는 감정을 없애려 하기보다, 중요한 결정 전에 잠시 멈추고 감정의 방향을 조정하는 시간이 필요합니다. "
            "감정 억제가 어려워지는 순간에는 판단과 실행을 잠시 미루고, 기록·대화·휴식처럼 흐름을 안정시키는 순서가 필요해보입니다."
        )

    if "회피성" in natures:
        lines.append(
            "회피형 흐름은 부담을 줄이는 기능으로 작용하지만, 반복되면 실행 연결이 약해질 수 있습니다. "
            "작은 일부터 하나씩 완료하는 방식으로 실천의 연결고리를 만드는 것이 필요합니다."
        )

    if "저활력성" in natures or "피로민감성" in natures:
        lines.append(
            "활력 저하나 피로 민감성이 있을 때는 의지보다 리듬 조정이 먼저입니다. "
            "무리한 확장보다 수면·휴식·작은 실행 단위를 안정시키는 방향 조절이 전체 흐름을 회복하는 데 도움이 됩니다."
        )

    if "고활력성" in natures or "추진력" in natures or "주도성" in natures:
        lines.append(
            "추진 흐름이 강할 때는 속도보다 방향 정리가 중요합니다. "
            "실행 전에 우선순위를 좁히면 에너지가 분산되지 않고 성과로 연결되기 쉽습니다."
        )

    if "분석력" in natures or "전략성" in natures or "논리성" in natures:
        lines.append(
            "분석과 전략 흐름이 강할 때는 생각이 깊어져 실행이 늦어지므로, 기준을 정하여 실행으로 옮기는 순서가 필요합니다."
        )

    if not lines:
        lines.append(
            "현재는 특정 본성을 억누르기보다, 강하게 작용하는 성향이 실행괴 생활 리듬으로 자연스럽게 이어지도록 정리하는 것이 좋습니다."
        )

    return "\n\n".join(lines)



# =========================================================
# 10-1. 영문 결과 출력 보조
# =========================================================

def get_output_language(input_data: Dict[str, Any]) -> str:
    """
    UI에서 전달된 언어 값을 확인한다.
    - app/index.html이 lang, language, ui_lang 중 하나로 전달해도 동작하게 한다.
    - 값이 없으면 한국어 기본 출력.
    """
    if not isinstance(input_data, dict):
        return "ko"

    raw = input_data.get("raw", {})
    candidates = [
        input_data.get("lang"),
        input_data.get("language"),
        input_data.get("ui_lang"),
    ]

    if isinstance(raw, dict):
        candidates.extend([
            raw.get("lang"),
            raw.get("language"),
            raw.get("ui_lang"),
        ])
    elif hasattr(raw, "get"):
        candidates.extend([
            raw.get("lang", None),
            raw.get("language", None),
            raw.get("ui_lang", None),
        ])

    for value in candidates:
        text = safe_text(value).lower()
        if text in ["en", "english"]:
            return "en"
        if text in ["ko", "kr", "korean"]:
            return "ko"

    return "ko"


EN_SCORE_LABELS = {
    "매우 안정": "highly stable",
    "안정": "stable",
    "다소 안정": "moderately stable",
    "다소 불안정": "moderately unstable",
    "매우 불안정": "highly unstable",
}

EN_FINAL_DECISIONS = {
    "개선 중심": "improvement-oriented",
    "유지 중심": "maintenance-oriented",
    "위협 관리": "threat-management",
    "혼합 상태": "mixed",
    "개선 권장": "improvement recommended",
    "유지 권장": "maintenance recommended",
}

EN_FLOW_NAMES = {
    "개선 흐름": "Improvement flow",
    "유지 흐름": "Maintenance flow",
    "위협 흐름": "Threat flow",
    "개선 경로": "Improvement flow",
    "유지 경로": "Maintenance flow",
    "위협 경로": "Threat flow",
    "완만 개선": "Gradual improvement flow",
    "완만 위협": "Gradual threat flow",
}

EN_ESSENCE_TERMS = {
    "적응성": "Adaptability",
    "학습성": "Learning orientation",
    "관계성": "Relational orientation",
    "표현성": "Expressive orientation",
    "추진성": "Drive",
    "안전성": "Safety orientation",
    "반응성": "Responsiveness",
    "남성성": "Masculine tendency",
    "여성성": "Feminine tendency",
}

EN_NATURE_TERMS = {
    "실행성": "Execution",
    "도전성": "Challenge orientation",
    "추진력": "Drive",
    "주도성": "Initiative",
    "책임감": "Responsibility",
    "능동성": "Proactivity",
    "경쟁성": "Competitiveness",
    "분석력": "Analytical ability",
    "탐구성": "Inquiry orientation",
    "판단력": "Judgment",
    "창의성": "Creativity",
    "논리성": "Logical thinking",
    "직관력": "Intuition",
    "관계지향": "Relationship orientation",
    "관계지향성": "Relationship orientation",
    "관계융화": "Relational harmony",
    "관계조화성": "Relational harmony",
    "영향력": "Influence",
    "공감성": "Empathy",
    "소통성": "Communication",
    "포용성": "Inclusiveness",
    "표현력": "Expressiveness",
    "이해력": "Understanding",
    "자기표현성": "Self-expression",
    "안정지향성": "Stability orientation",
    "변화지향성": "Change orientation",
    "확장성": "Expansion orientation",
    "확장형": "Expansion orientation",
    "보수성": "Conservativeness",
    "위험회피성": "Risk avoidance",
    "욕구강조성": "Desire emphasis",
    "불안민감성": "Anxiety sensitivity",
    "자기중심성": "Self-centered tendency",
    "감정변동성": "Emotional fluctuation",
    "스트레스민감성": "Stress sensitivity",
    "비교민감성": "Comparison sensitivity",
    "신중성": "Carefulness",
    "직관성": "Intuitive decision style",
    "분석성": "Analytical decision style",
    "회피성": "Avoidance tendency",
    "전략성": "Strategic thinking",
    "즉흥형": "Impulsiveness",
    "결단형": "Decisiveness",
    "고활력성": "High energy",
    "지속성": "Persistence",
    "저활력성": "Low energy",
    "활력변동성": "Energy fluctuation",
    "집중성": "Concentration",
    "집중형": "Concentration",
    "피로민감성": "Fatigue sensitivity",
    "리듬안정성": "Rhythm stability",
}

EN_AXIS_TERMS = {
    "연구·분석형": "Research / Analytical",
    "전략·참모형": "Strategic / Advisory",
    "실행·사업형": "Execution / Business",
    "관계·중재형": "Relational / Mediation",
    "표현·창작형": "Expression / Creative",
    "관리·안정형": "Management / Stability",
    "감지·직관형": "Sensing / Intuitive",
}

EN_JOB_TERMS = {
    "연구원": "researcher",
    "분석가": "analyst",
    "데이터/정책 분석": "data / policy analyst",
    "기획자": "planner",
    "컨설턴트": "consultant",
    "교수/강의": "professor / lecturer",
    "전문 평가/심사": "expert evaluator / reviewer",
    "조사/분석 기획": "research / analysis planner",
    "전략가": "strategist",
    "전략기획": "strategic planning",
    "정책기획": "policy planning",
    "자문": "advisor",
    "조직 설계": "organizational design",
    "보좌/참모": "staff / advisory role",
    "중장기 기획": "mid- to long-term planning",
    "사업 기획": "business planning",
    "운영 전략 설계": "operation strategy design",
    "사업가": "entrepreneur",
    "영업 리더": "sales leader",
    "프로젝트 리더": "project leader",
    "운영 총괄": "operations lead",
    "현장 책임자": "site / field manager",
    "추진형 관리자": "execution-oriented manager",
    "개척형 역할": "pioneering role",
    "성과 중심 실무": "performance-oriented work",
    "상담": "counseling",
    "코칭": "coaching",
    "교육": "education",
    "HR": "HR",
    "협상": "negotiation",
    "조직 조정": "organizational coordination",
    "커뮤니티 운영": "community management",
    "대외 협력": "external cooperation",
    "고객 관계 관리": "customer relationship management",
    "작가": "writer",
    "디자이너": "designer",
    "콘텐츠 제작": "content creation",
    "예술/문화 기획": "arts / culture planning",
    "브랜딩": "branding",
    "스토리텔링": "storytelling",
    "강연/표현형": "speaking / presentation role",
    "홍보 콘텐츠 기획": "PR content planning",
    "행정": "administration",
    "운영": "operations",
    "관리": "management",
    "재무/회계": "finance / accounting",
    "품질 관리": "quality management",
    "유지보수": "maintenance",
    "자원 관리": "resource management",
    "프로세스 운영": "process operation",
    "안정화 역할": "stabilization role",
    "리스크 감지": "risk sensing",
    "위기 대응 보조": "crisis-response support",
    "모니터링": "monitoring",
    "상황 판단 지원": "situation-judgment support",
    "기획 보조": "planning support",
    "탐지/관찰형 업무": "detection / observation work",
    "조기 경보 역할": "early-warning role",
    "패턴 파악 업무": "pattern recognition work",
}

def en_score_label(score: float) -> str:
    return EN_SCORE_LABELS.get(score_to_label(score), score_to_label(score))


def en_term(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if text in EN_ESSENCE_TERMS:
        return EN_ESSENCE_TERMS[text]
    if text in EN_NATURE_TERMS:
        return EN_NATURE_TERMS[text]
    if text in EN_AXIS_TERMS:
        return EN_AXIS_TERMS[text]
    if text in EN_FLOW_NAMES:
        return EN_FLOW_NAMES[text]
    if text in EN_FINAL_DECISIONS:
        return EN_FINAL_DECISIONS[text]
    if text in EN_JOB_TERMS:
        return EN_JOB_TERMS[text]
    return text


def en_join_terms(values: Any) -> str:
    items = flatten_selected(values)
    translated = [en_term(x) for x in items if safe_text(x)]
    return ", ".join(translated)


def translate_vector_to_english(item: Dict[str, Any], vector_type: str) -> Dict[str, Any]:
    new_item = dict(item)
    factor = safe_text(new_item.get("factor"))
    score = new_item.get("score", 0)

    factor_map = {
        "건강·정서 안정 보완": "emotional stability",
        "실행 연결 부족": "execution gap",
        "생각 정리·판단 혼선": "judgment confusion",
        "관계 부담": "Relationship burden",
        "현실 여건 압박": "External pressure",
        "건강·안정 기반": "stability base",
        "실행 추진 자원": "Execution drive",
        "사고·판단 자원": "Cognitive resource",
        "관계·연결 자원": "Relational resource",
        "환경 지원": "Environmental support",
        "경험 축적": "Accumulated experience",
    }

    if factor in factor_map:
        new_factor = factor_map[factor]
    elif "실천 연결 부족" in factor:
        essence = factor.replace("실천 연결 부족", "").strip()
        new_factor = f"{en_term(essence)} alignment gap".strip()
    elif "활용 강점" in factor:
        essence = factor.replace("활용 강점", "").strip()
        new_factor = f"{en_term(essence)} usable strength".strip()
    else:
        new_factor = en_term(factor)

    new_item["factor"] = new_factor

    if vector_type == "threat":
        new_item["rationale"] = (
            "This factor may weaken the current flow if it remains unsupported."
        )
    else:
        new_item["rationale"] = (
            "This factor can serve as a useful resource when it is connected to realistic action."
        )

    try:
        new_item["score"] = round(float(score), 1)
    except Exception:
        new_item["score"] = score

    return new_item


def translate_result_to_english(input_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    한국어 엔진 계산은 유지하되, 사용자가 영어 UI를 선택한 경우
    주요 결과 문장을 자연스러운 영어 서술로 재생성한다.
    """
    if not isinstance(result, dict):
        return result

    root_state = result.get("root_state", {}) or {}
    root_score = normalize_score(result.get("root_score", 50), 50)
    hw = normalize_score(result.get("hw_score", 50), 50)
    sw = normalize_score(result.get("sw_score", 50), 50)
    env = normalize_score(result.get("environment_score", 50), 50)
    exp = normalize_score(result.get("experience_score", 50), 50)

    stability = normalize_score(root_state.get("stability", root_score), root_score)
    drive = normalize_score(root_state.get("drive", sw), sw)
    cognition = normalize_score(root_state.get("cognition", sw), sw)
    relation = normalize_score(root_state.get("relation", exp), exp)

    final_decision_ko = safe_text(result.get("final_decision") or (result.get("path_decision", {}) or {}).get("final_decision", ""))
    final_decision_en = en_term(final_decision_ko) or "mixed"

    essences = input_data.get("essences", [])
    natures = input_data.get("natures", [])
    essence_text = en_join_terms(essences) or "not specified"
    nature_text = en_join_terms(natures) or "not specified"

    result["one_line_summary"] = (
        f"The current overall state is {en_score_label(root_score)}. "
        f"The dominant direction is {final_decision_en}, and the next step is to connect core tendencies with realistic conditions."
    )

    result["current_status_text"] = (
        f"The current state is {en_score_label(root_score)} overall.\n"
        f"Health / stability is {en_score_label(stability)} ({stability:.1f}%), "
        f"execution drive is {en_score_label(drive)} ({drive:.1f}%).\n"
        f"Cognitive / judgment flow is {en_score_label(cognition)} ({cognition:.1f}%), "
        f"and relational flow is {en_score_label(relation)} ({relation:.1f}%).\n"
        f"The selected essences are {essence_text}. The selected current natures are {nature_text}."
    )

    # Vector translation
    result["threat_vectors"] = [
        translate_vector_to_english(item, "threat")
        for item in (result.get("threat_vectors", []) or [])
        if isinstance(item, dict)
    ]
    result["opportunity_vectors"] = [
        translate_vector_to_english(item, "opportunity")
        for item in (result.get("opportunity_vectors", []) or [])
        if isinstance(item, dict)
    ]

    top_threat = result["threat_vectors"][0] if result.get("threat_vectors") else {}
    top_opp = result["opportunity_vectors"][0] if result.get("opportunity_vectors") else {}

    if top_threat:
        result["core_problem_text"] = (
            f"The main point to examine is '{top_threat.get('factor')}'. "
            "In RAIS terms, this is not simply a weakness. It indicates a point where the original essence and the current nature "
            "are not yet fully connected to stable action or real-world conditions."
        )
    else:
        result["core_problem_text"] = (
            "The core issue is not a single defect. It is better understood as the degree to which essence, current nature, "
            "and real-world conditions are aligned."
        )

    path_distribution = result.get("path_distribution", {}) or {}
    improve = normalize_score(path_distribution.get("개선 흐름", path_distribution.get("개선 경로", 0)), 0)
    maintain = normalize_score(path_distribution.get("유지 흐름", path_distribution.get("유지 경로", 0)), 0)
    threat = normalize_score(path_distribution.get("위협 흐름", path_distribution.get("위협 경로", 0)), 0)

    flows = [
        ("Threat flow", threat),
        ("Maintenance flow", maintain),
        ("Improvement flow", improve),
    ]
    flows_sorted = sorted(flows, key=lambda x: x[1], reverse=True)

    result["future_flow_text"] = (
        f"The final assessment is [{final_decision_en}]. "
        "Improvement, maintenance, and threat factors coexist, but the relative weight of each flow should be read as a structural tendency rather than a fixed prediction.\n"
        f"The first flow is {flows_sorted[0][0]} ({flows_sorted[0][1]:.1f}%). "
        f"The second flow is {flows_sorted[1][0]} ({flows_sorted[1][1]:.1f}%). "
        f"The supplemental flow is {flows_sorted[2][0]} ({flows_sorted[2][1]:.1f}%).\n"
        "If environmental support and execution alignment improve, the threat tendency can be reduced and the improvement tendency can gradually increase."
    )

    talent_scores = result.get("talent_axis_scores", {}) or {}
    if talent_scores:
        top_axes = sorted(talent_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        axis_text = "\n".join([f"- {en_term(axis)}: {score:.1f}" for axis, score in top_axes])
        result["talent_analysis_text"] = (
            "The strongest talent directions are:\n"
            f"{axis_text}\n"
            "These scores should be read as tendency indicators, not as fixed career labels."
        )

        # recommended axes도 영어 표시용으로 보조 필드 추가
        result["recommended_axes_en"] = [(en_term(axis), score) for axis, score in top_axes]
    else:
        result["talent_analysis_text"] = (
            "The talent-axis analysis is not strong enough to determine a single direction. "
            "It is better to review the balance between cognition, execution, relation, and stability."
        )

    current_fit = result.get("current_job_fit", {}) or {}
    fit_label = safe_text(current_fit.get("fit_label"))
    fit_score = current_fit.get("fit_score")
    fit_axis = en_term(current_fit.get("current_job_axis", ""))

    fit_label_map_en = {
        "잘 맞음": "well aligned",
        "부분적으로 맞음": "partially aligned",
        "현 본성과 맞지 않는 상태": "not yet well aligned with the current nature flow",
        "비교 정보 부족": "insufficient information",
        "진로 탐색 단계": "career exploration stage",
        "전환기 상태": "transition stage",
        "유동적 직업 상태": "flexible work state",
    }

    fit_label_en = fit_label_map_en.get(fit_label, fit_label)

    if fit_score is not None:
        result["current_fit_text"] = (
            f"The current role appears to be connected to the {fit_axis} axis. "
            f"The fit level is {fit_label_en} ({fit_score}). "
            "This should be understood as a reference for role alignment, not as an absolute judgment."
        )
    else:
        result["current_fit_text"] = (
            "The current role cannot be judged as a fixed career fit. "
            "It is more useful to review which activity structure best supports the selected essence and current nature."
        )

    recommended_lines = []
    if talent_scores:
        for axis, _score in sorted(talent_scores.items(), key=lambda x: x[1], reverse=True)[:3]:
            group = JOB_GROUPS.get(axis, {})
            jobs = [en_term(job) for job in group.get("jobs", [])[:5]]
            if jobs:
                recommended_lines.append(f"- {en_term(axis)}: {', '.join(jobs)}")
    result["recommended_jobs_text"] = (
        "Recommended activity or role directions:\n"
        + ("\n".join(recommended_lines) if recommended_lines else "- Review activity directions after adding more input.")
    )

    if top_threat and top_opp:
        result["nature_change_text"] = (
            f"First, reduce the burden related to '{top_threat.get('factor')}'. "
            f"At the same time, use '{top_opp.get('factor')}' as a supporting resource.\n"
            "Rather than making a large decision immediately, start with a small change in current nature and observe how the flow changes."
        )
    elif top_threat:
        result["nature_change_text"] = (
            f"First, reduce the burden related to '{top_threat.get('factor')}'. "
            "A small and repeated adjustment is more suitable than an abrupt decision."
        )
    else:
        result["nature_change_text"] = (
            "The next step is to connect the selected essence and current nature to small, realistic actions. "
            "The goal is not to force a personality change, but to create a more stable flow."
        )

    result["common_comment_text"] = (
        "This result is a reference interpretation based on the selected essence, current nature, current state, and experience pattern. "
        "The important point is not whether the result is absolutely right or wrong, but how the selected root elements and conditions create a certain flow."
    )

    result["result_language"] = "en"
    return result


def polish_english_text(text: str) -> str:
    """
    AI 또는 번역 후처리에서 남을 수 있는 직역 표현을 정리한다.
    """
    text = safe_text(text)
    replacements = {
        "behavior connection": "behavioral alignment",
        "action connection": "behavioral alignment",
        "activation": "emerging tendency",
        "expression": "manifested tendency",
        "strengthening threat flow": "increasing threat tendency",
        "threat flow": "threat tendency",
        "improvement flow": "improvement tendency",
        "maintenance flow": "maintenance tendency",
        "Root Analysis Intelligence System": "Root Analysis Intelligence System",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def post_process_result(input_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    def clean_text(text: str) -> str:
        text = safe_text(text)

        replacements = {
            "발현": "살아나는 방식",
            "살아나는 방식 방식": "살아나는 방식",
            "충분히 살아나지 못하고 있습니다": "강점이 충분히 살아나지 못하고 있습니다",
            "강점이 충분히 발현되지 못하는 요소도 함께 섞여 있습니다": "강점이 실제 역할에서 충분히 살아나지 않는 요소도 함께 있습니다",
            "구조적 불일치": "현재 본성과 맞지 않는 부분",
            "방어와 보강": "보완과 조정",
            "방어하기 보다": "억누르기보다",
            "방어하기보다": "억누르기보다",
            "방어적 태도": "위축된 태도",
            "방어": "보완",
            "감정 흐름": "감정 변화의 기복",
            "감정 흐름이 커지면": "감정 억제가 어려워지면",
            "감정 변화의 기복이 커지면": "감정 억제가 어려워지면",
            "반대로 감정 변동성:": "감정 변동성:",
            "본성은 중요한 강점으로 작용합니다": "이 성향은 상황을 읽고 조정하는 데 도움이 될 수 있습니다",
            "방식과도 연결됩니다": "흐름과도 연결됩니다",
            "'현 직업 유지'을": "'현 직업 유지'를",
            "'새 직업 탐색'을": "'새 직업 탐색'을",
            "활용이 충분히 이루어지지 않는 상태": "활용 여지",
            "바로 실천으로 이어지지 않는 흐름": "실천 연결 부족",
            "실천으로 이어지지 않는 흐름": "실천 연결 부족",
            "실제 행동으로 이어지지 않는 흐름": "행동 연결 부족",
            "점진적 행동 연결 시도": "점진적인 본성 변화 가능성",
            "남성성 발현 억제": "남성성이 다소 억눌려 있는 상태",
            "여성성 발현 억제": "여성성이 다소 억눌려 있는 상태",
            "부분적으로 맞음": "부분 적합",
            "잘 맞음": "잘 맞음",
            "현 본성과 맞지 않는 상태": "현 본성과 맞지 않는 상태",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        while "  " in text:
            text = text.replace("  ", " ")

        return text.strip()

    def clean_vector_label(text: str) -> str:
        text = safe_text(text)
        replacements = {
            "은 가지고 있지만, 바로 실천으로 이어지지 않는 흐름": " 실천 연결 부족",
            "은 가지고 있지만, 실천으로 이어지지 않는 흐름": " 실천 연결 부족",
            "활용이 충분히 이루어지지 않는 상태": "활용 여지",
            "자연스럽게 나타나는": "활용 강점",
            "건강/정서 안정": "건강·정서 안정",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.strip()

    for vector_key in ["threat_vectors", "opportunity_vectors"]:
        cleaned = []
        seen = set()
        for item in result.get(vector_key, []) or []:
            if not isinstance(item, dict):
                continue
            new_item = dict(item)
            new_item["factor"] = clean_vector_label(new_item.get("factor", ""))
            new_item["rationale"] = clean_text(new_item.get("rationale", ""))
            sig = new_item.get("factor")
            if sig and sig not in seen:
                seen.add(sig)
                cleaned.append(new_item)
        result[vector_key] = cleaned

    for field in [
        "one_line_summary",
        "current_status_text",
        "core_problem_text",
        "future_flow_text",
        "talent_analysis_text",
        "current_fit_text",
        "recommended_jobs_text",
        "nature_change_text",
        "common_comment_text",
    ]:
        if field in result:
            result[field] = clean_text(result.get(field))

    result["core_problem_text"] = build_core_problem_text(input_data, result)
    result["core_problem_text"] = clean_text(result["core_problem_text"])

    result["nature_change_text"] = build_nature_change_text(input_data, result)
    result["nature_change_text"] = clean_text(result["nature_change_text"])

    result["common_comment_text"] = (
        "이 결과는 입력된 본질과 본성의 조합이 현재 상태와 미래 흐름으로 어떻게 연결되는지를 해석한 참고 자료입니다. "
        "중요한 것은 결과의 맞고 틀림보다, 어떤 선택과 조건이 어떤 흐름을 만드는지 이해하는 것입니다. "
        "결과가 다르게 느껴진다면, 본성 선택이나 현재 상태 입력을 조금 더 냉정하게 다시 확인해보는 것도 도움이 됩니다."
    )

    if get_output_language(input_data) == "en":
        result = translate_result_to_english(input_data, result)
        for field in [
            "one_line_summary",
            "current_status_text",
            "core_problem_text",
            "future_flow_text",
            "talent_analysis_text",
            "current_fit_text",
            "recommended_jobs_text",
            "nature_change_text",
            "common_comment_text",
        ]:
            if field in result:
                result[field] = polish_english_text(result.get(field))

    return result

# =========================================================
# 11. 메인 엔진
# =========================================================

def build_ra_result(raw_input_data: Dict[str, Any]) -> Dict[str, Any]:
    data = normalize_input_data(raw_input_data)
    name = data.get("name", "사용자")

    alignment_map = compute_essence_alignment(data)
    alignment_overview = compute_alignment_overview(data, alignment_map)
    conflicts = detect_essence_conflicts(data, alignment_map)

    root = compute_root_state(data, alignment_map)
    env = compute_environment_support(data)
    hw = compute_hw_score(data)
    sw = compute_sw_score(data)
    exp = compute_experience_score(data)

    threat_vectors = compute_threat_vectors(data, root, alignment_map)
    opportunity_vectors = compute_opportunity_vectors(data, root, alignment_map)
    path_distribution = build_path_distribution(root, env, alignment_map)
    path_decision = evaluate_path_decision(path_distribution)
    path_explanations = build_path_explanations(path_distribution)

    talent_scores = compute_talent_axis_scores(data, root, alignment_map)
    current_fit = evaluate_current_job_fit(data.get("current_job", ""), talent_scores)
    alignment_summary = build_alignment_summary(data, alignment_map)

    result = {
        "engine": MODEL_VERSION,
        "framework": "Origin → Root → Sub(HW/SW/Environment/Experience)",
        "name": name,
        "input_normalized": data,

        "hw_score": round(hw, 1),
        "sw_score": round(sw, 1),
        "environment_score": round(env, 1),
        "experience_score": round(exp, 1),

        "root_score": round(avg([root.stability, root.drive, root.cognition, root.relation], 50), 1),
        "root_state": asdict(root),

        "origin_root_alignment": alignment_summary,
        "alignment_overview": alignment_overview,
        "conflicts": conflicts,

        "threat_vectors": threat_vectors,
        "opportunity_vectors": opportunity_vectors,

        "path_distribution": path_distribution,
        "path_decision": path_decision,
        "final_decision": path_decision["final_decision"],
        "path_explanations": path_explanations,

        "talent_axis_scores": talent_scores,
        "current_job_fit": current_fit,
        "recommended_axes": top_n_items(talent_scores, 5),

        "one_line_summary": build_one_line_summary(name, root, path_decision["final_decision"]),
        "current_status_text": build_current_status_text(name, data, root, opportunity_vectors),
        "core_problem_text": "",  #build_core_problem_text(threat_vectors, alignment_map, conflicts),
        "future_flow_text": build_future_flow_text(path_decision, path_explanations),
        "talent_analysis_text": build_talent_analysis_text(talent_scores),
        "current_fit_text": build_current_fit_text(current_fit),
        "recommended_jobs_text": build_recommended_jobs_text(talent_scores, raw_input_data),
        "nature_change_text": "",

        "common_comment_text": "이 결과는 현재 선택한 본질과 본성의 조합을 바탕으로 해석한 흐름입니다. 결과가 다르게 느껴진다면, 본성 선택을 조금 더 냉정하게 다시 확인해보는 것도 도움이 됩니다.",
    }

    job_context = classify_job_context(data.get("current_job", ""))

    # -----------------------------
    # v3 구조 분기
    # -----------------------------
    if job_context == "student":
        result["result_type"] = "student"
        result["section_title_6"] = "진로 방향 설계"
        result["section_title_7"] = "탐색 분야 제안"

        # 기존 문장 덮어쓰기
        result["current_fit_text"] = (
            "현재는 직업 적합도를 판단하는 단계가 아니라, "
            "본질과 본성에 맞는 진로 방향을 탐색하는 것이 중요한 시기입니다."
        )

        result["recommended_jobs_text"] = (
            "현재는 특정 직업을 바로 확정하기보다, 아래 재능 축을 기준으로 "
            "다양한 경험과 활동을 통해 방향을 탐색하는 것이 좋습니다.\n\n"
            + result.get("recommended_jobs_text", "")
        )

    elif job_context == "transition":
        result["result_type"] = "transition"
        result["section_title_6"] = "다음 방향 설계"
        result["section_title_7"] = "적합 활동 제안"

        result["current_fit_text"] = (
            "현재는 직업 적합도보다, 다음 삶의 방향과 구조를 재설계하는 것이 중요한 시기입니다."
        )

        result["recommended_jobs_text"] = (
            "현재는 재취업 자체보다, 자신의 강점이 살아나는 활동 방식과 방향을 먼저 정리하는 것이 중요합니다.\n\n"
            + result.get("recommended_jobs_text", "")
        )

    else:
        result["result_type"] = "regular"
    return post_process_result(data, result)

def build_fallback_result(input_data: Dict[str, Any]) -> Dict[str, Any]:
    name = input_data.get("name", "")

    return {
        "engine": MODEL_VERSION if "MODEL_VERSION" in globals() else "RAIS",
        "name": name,
        "one_line_summary": "기본 해석을 바탕으로 결과를 생성했습니다.",
        "current_status_text": "분석 중 일부 오류가 발생하여 기본 해석으로 전환했습니다.",
        "core_problem_text": "입력 상태 또는 일부 계산 과정에 보완이 필요할 수 있습니다.",
        "future_flow_text": "현재는 전체 흐름을 단정하기보다 입력과 엔진 연결 상태를 먼저 점검하는 편이 좋습니다.",
        "talent_analysis_text": "재능 축 분석은 기본 상태로 표시됩니다.",
        "current_fit_text": "현재 직업 적합도 비교는 기본 상태로 표시됩니다.",
        "recommended_jobs_text": "",
        "nature_change_text": "입력 상태를 다시 확인한 뒤 필요한 행동 조정 방향을 점검해보는 것이 좋습니다.",
        "path_distribution": {},
        "path_decision": {"final_decision": "점검 필요"},
        "final_decision": "점검 필요",
        "threat_vectors": [],
        "opportunity_vectors": [],
        "origin_root_alignment": [],
        "talent_axis_scores": {},
        "current_job_fit": {},
    }

# =========================================================
# 12. 간단 테스트
# =========================================================

# 최종 배포본에서는 sample_input 테스트 블록을 제거했습니다.
