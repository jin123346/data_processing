import pandas as pd
import numpy as np
import re
import traceback



def convert_to_gbif(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터를 GBIF 형식으로 변환합니다.
    GBIF 표준 필드에 맞게 데이터를 재구성합니다.
    """
    # GBIF 표준 필드 (예시)
    gbif_columns = [
        'occurrenceID',
        'basisOfRecord',
        'scientificName',
        'kingdom',
        'phylum',
        'class',
        'order',
        'family',
        'genus',
        'species',
        'decimalLatitude',
        'decimalLongitude',
        'countryCode',
        'locality',
        'eventDate',
        'recordedBy',
        'institutionCode',
        'collectionCode'
    ]
    
    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame()
    
    # 기존 데이터의 컬럼을 GBIF 형식에 매핑
    # 실제 매핑은 데이터 구조에 따라 조정이 필요합니다
    column_mapping = {}
    
    # 기본 매핑 시도 (대소문자 무시)
    for gbif_col in gbif_columns:
        for orig_col in df.columns:
            if gbif_col.lower() in orig_col.lower() or orig_col.lower() in gbif_col.lower():
                column_mapping[gbif_col] = orig_col
                break
    
    # 매핑된 컬럼 복사
    for gbif_col in gbif_columns:
        if gbif_col in column_mapping:
            result_df[gbif_col] = df[column_mapping[gbif_col]]
        else:
            result_df[gbif_col] = np.nan
    
    return result_df


"""
    네이버 백과사전 형식으로 변환
    데이터를 네이버백과 전처리 규칙에 맞춰 변환합니다.
    제공된 매핑 표를 기준으로 단순 매핑 및 복수 컬럼 분리(생태적특징, 일반적 특징)를 수행합니다.
"""

COL_ID = 'id'
COL_LATIN = '분류체계명(라틴)'
COL_KOREAN = '분류체계명(국문)'
COL_GROUP = '분류군'
COL_SCIENTIFIC = '학명'
COL_COMMON = '국명'
COL_UPDATE = '업데이트'
COL_PROTECTED_NATURAL = '천년기념물'
COL_ENDANGERED = '멸종위기종'
COL_PROTECTED_PLANT = '보호식물명'
COL_ECO_HABITAT = '서식지'
COL_ECO_DIET = '먹이습성'
COL_ECO_BEHAVIOR = '행동습성'
COL_ECO_DOMESTIC = '국내분포'
COL_ECO_OVERSEAS = '국외분포'
COL_GENERAL_SIZE = '크기'
COL_GENERAL_TRAIT = '주요형질'
COL_ECO_RAW = '생태적특징'
COL_GENERAL_RAW = '일반적 특징'
SRC_ECO_FEATURE = '생태적특징'
SRC_GENERAL_FEATURE = '일반적특징'
LABEL_SUFFIX_CHARS = ' 는은이가:-'
SIZE_KEYWORDS = ['크기', '몸길이', '체장', '길이', '전장', '체고']

def _is_empty(value):
    return pd.isna(value) or not str(value).strip()


def _normalize_identifier(name: str) -> str:
    if name is None:
        return ''
    normalized = ''.join(ch for ch in str(name).strip() if ch not in [' ', '\t'])
    normalized = normalized.replace(':', '').lower()
    return normalized


def _build_label_lookup(section_variants):
    lookup = {}
    for target_col, variants in section_variants.items():
        for variant in variants:
            lookup[_normalize_identifier(variant)] = (target_col, variant.strip())
    return lookup


def _split_sections(text_str: str):
    normalized_text = text_str.replace('\r', '\n')
    normalized_text = normalized_text.replace('||', '\n')
    normalized_text = normalized_text.replace('：', ':')
    # 줄/구분자 기준으로 쪼갬
    segments = re.split(r'\n+', normalized_text)

    return [segment.strip() for segment in segments if segment and segment.strip()]


def _resolve_label_value(piece: str, label_lookup):
    if ':' in piece:
        label_part, value_part = piece.split(':', 1)
        return label_part, value_part
    
    for _, (_, raw_label) in label_lookup.items():
        if piece.startswith(raw_label):
            value_part = piece[len(raw_label):].lstrip(LABEL_SUFFIX_CHARS)
            return raw_label, value_part
        if piece.startswith(raw_label.replace(' ', '')):
            value_part = piece[len(raw_label.replace(' ', '')):].lstrip(LABEL_SUFFIX_CHARS)
            return raw_label, value_part
    return None, None


def _parse_section_text(text, label_lookup, target_columns):
    parsed = {target: np.nan for target in target_columns}
    if pd.isna(text):
        return parsed
    text_str = str(text).strip()
    if not text_str:
        return parsed
    
    segments = _split_sections(text_str)
    for piece in segments:
        label_part, value_part = _resolve_label_value(piece, label_lookup)
        if not label_part:
            continue
        
        label_norm = _normalize_identifier(label_part)
        if label_norm not in label_lookup:
            continue
        
        target_col, _ = label_lookup[label_norm]
        if target_col not in parsed:
            continue
        
        value_clean = value_part.strip() if value_part else ''
        if value_clean and pd.isna(parsed[target_col]):
            parsed[target_col] = value_clean
    
    return parsed


def _apply_direct_mapping(df, normalized_columns, mapping):
    result = {}
    for source_key, target_col in mapping.items():
        source_col = normalized_columns.get(source_key)
        if source_col:
            result[target_col] = df[source_col]
        else:
            result[target_col] = pd.Series([np.nan] * len(df), index=df.index)
    return pd.DataFrame(result)


def _extract_section_series(df, normalized_columns, source_key, section_variants):
    """
    생태적특징 / 일반적특징 같이 '복합 텍스트 컬럼'을
    여러 타겟 컬럼(서식지, 먹이습성, 행동습성, ...)으로 분리.

    1) 먼저 라벨 기반 파싱(_parse_section_text) 시도
    2) 결과가 전부 비어 있으면 → fallback 규칙으로 채우기
    """
    lookup = _build_label_lookup(section_variants)
    num_rows = len(df)
    values = {col: [np.nan] * num_rows for col in section_variants}
    source_col = normalized_columns.get(source_key)

    if not source_col:
        # 소스 컬럼 자체가 없으면 전부 NaN 유지
        return {col: pd.Series(vals, index=df.index) for col, vals in values.items()}

    series = df[source_col].fillna('')

    for idx, raw_text in enumerate(series):
        text_str = str(raw_text).strip()

        # 1) 라벨 기반 파싱 시도
        parsed = _parse_section_text(raw_text, lookup, section_variants.keys())

        # 2) 라벨 기반 결과가 전부 비어 있는지 확인
        all_empty = True
        for target_col in section_variants.keys():
            v = parsed.get(target_col, np.nan)
            if not _is_empty(v):
                all_empty = False
                break

        # 3) 라벨이 하나도 없고, 텍스트는 있을 때 → fallback
        if all_empty and text_str:
            # 생태적 특징일 때
            if source_key == SRC_ECO_FEATURE:
                # 네 데이터가 보통 '생태 전체 설명' 한 덩어리라서
                # 일단 서식지/행동습성/먹이습성에 모두 복사 (원하면 규칙 더 쪼갤 수 있음)
                eco_split = _heuristic_split_ecology(text_str)
                for col in section_variants.keys():
                    if col in eco_split and not _is_empty(eco_split[col]):
                        parsed[col] = eco_split[col]
                # 국내/국외 분포는 라벨 데이터가 따로 있는 경우만 쓰는 게 보통이라 비워둠

            # 일반적 특징일 때
            elif source_key == SRC_GENERAL_FEATURE:
                # 일반적 특징 전체를 "주요형질"로 일단 몰아넣고,
                # 나중에 _apply_general_text_heuristics 에서
                # 크기/주요형질 문장 분리
                target_trait = None
                for col in section_variants.keys():
                    if col == COL_GENERAL_TRAIT:
                        target_trait = col
                        break
                if target_trait is None:
                    # 그래도 뭔가 하나는 채워야 한다면, 그냥 첫 번째 컬럼에 넣기
                    target_trait = next(iter(section_variants.keys()))
                parsed[target_trait] = text_str

        # 4) 최종 값 저장
        for target_col in section_variants:
            values[target_col][idx] = parsed[target_col]

    # 5) dict[column] -> Series 로 변환
    return {col: pd.Series(vals, index=df.index) for col, vals in values.items()}

def _fill_fallback_values(result_df, df, normalized_columns, fallback_sources):
    for source_key, target_col in fallback_sources.items():
        source_col = normalized_columns.get(source_key)
        if source_col and target_col in result_df:
            result_df[target_col] = result_df[target_col].where(
                result_df[target_col].notna(),
                df[source_col]
            )


def _designation_label(value):
    if pd.isna(value):
        return '미지정'
    text = str(value).strip()
    return '지정' if text else '미지정'


def _apply_general_text_heuristics(result_df):
    has_general_raw = COL_GENERAL_RAW in result_df
    has_size = COL_GENERAL_SIZE in result_df
    
    sentence_splitter = re.compile(r'(?<=[.!?])\s*|\n+')
    mm_pattern = re.compile(r'(mm|㎜|cm|센티미터)', re.IGNORECASE)
    for idx in result_df.index:
        raw_text = None

        # 1) 일반적 특징이 있으면 우선 사용
        if has_general_raw:
            raw_text = result_df.at[idx, COL_GENERAL_RAW]

        # 2) 일반적 특징이 비어있고, 크기에 텍스트가 있으면 크기를 raw로 사용
        if _is_empty(raw_text) and has_size:
            raw_text = result_df.at[idx, COL_GENERAL_SIZE]

        # 3) 그래도 없으면 스킵
        if _is_empty(raw_text):
            continue

        # 4) raw가 비어있던 경우에는, 크기에서 가져온 값을 일반적 특징에도 넣어 둠
        if has_general_raw and _is_empty(result_df.at[idx, COL_GENERAL_RAW]):
            result_df.at[idx, COL_GENERAL_RAW] = raw_text

        _update_general_row(result_df, idx, raw_text, sentence_splitter, mm_pattern)
    
    # for idx, raw_text in result_df[COL_GENERAL_RAW].items():
    #     _update_general_row(result_df, idx, raw_text, sentence_splitter, mm_pattern)


def _update_general_row(result_df, idx, raw_text, sentence_splitter, mm_pattern):
    if _is_empty(raw_text):
        return

    # 기존 값은 참고용으로만 읽고
    size_value = result_df.at[idx, COL_GENERAL_SIZE] if COL_GENERAL_SIZE in result_df else None
    trait_value = result_df.at[idx, COL_GENERAL_TRAIT] if COL_GENERAL_TRAIT in result_df else None

    size_candidate, trait_candidate = _derive_general_values(raw_text, sentence_splitter, mm_pattern)

    # 🔴 크기는 항상 패턴 인식 결과로 덮어쓰기
    if size_candidate:
        result_df.at[idx, COL_GENERAL_SIZE] = size_candidate

    # 🔴 주요형질도 결과가 있으면 덮어쓰기(또는 없을 때만 채우고 싶으면 조건 바꿔도 됨)
    if trait_candidate:
        result_df.at[idx, COL_GENERAL_TRAIT] = trait_candidate


def _derive_general_values(raw_text, sentence_splitter, mm_pattern):
    size_sentence, trait_text = _infer_general_sentences(raw_text, sentence_splitter, mm_pattern)
    
    size_result = None
    trait_result = None
    
    if size_sentence:
        cleaned_size = _strip_label_prefix(size_sentence, SIZE_KEYWORDS)
        size_result = _format_size_text(cleaned_size or size_sentence, size_sentence)
    
    if trait_text:
        cleaned_trait = _strip_label_prefix(trait_text, ['주요 형질', '주요형질'])
        trait_result = cleaned_trait or trait_text
    
    return size_result, trait_result


def _infer_general_sentences(raw_text, splitter, mm_pattern):
    sentences = splitter.split(str(raw_text).strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return None, None
    
    size_index = _locate_size_sentence(sentences, mm_pattern)
    leftover = None
    
    if size_index is not None:
        size_sentence = sentences[size_index]
        size_sentence, leftover = _split_size_sentence(size_sentence)
        remaining = sentences[:size_index] + sentences[size_index + 1:]
    else:
        size_sentence = None
        remaining = sentences[1:]
    
    if leftover:
        remaining.insert(0, leftover.strip())
    
    trait_text = ' '.join(remaining).strip() if remaining else None
    return size_sentence, (trait_text or None)


def _strip_label_prefix(text, labels):
    stripped = text.strip()
    for label in labels:
        variations = [label, label.replace(' ', '')]
        for variation in variations:
            if stripped.startswith(variation):
                return stripped[len(variation):].lstrip(LABEL_SUFFIX_CHARS)
    return stripped


def _locate_size_sentence(sentences, mm_pattern):
    for idx, sentence in enumerate(sentences):
        normalized_sentence = sentence.strip()
        if mm_pattern.search(normalized_sentence):
            return idx
        if any(normalized_sentence.startswith(keyword) for keyword in SIZE_KEYWORDS):
            return idx
    return None


def _format_size_text(cleaned_text, original_sentence):
    clean = cleaned_text.strip()
    original = (original_sentence or '').strip()
    if not clean:
        return clean
    if original and any(original.startswith(keyword) for keyword in SIZE_KEYWORDS):
        return original
    if any(clean.startswith(keyword) for keyword in SIZE_KEYWORDS):
        return clean
    return f"크기는 {clean}"


def _split_size_sentence(sentence):
    text = sentence.strip()
    if not text:
        return text, ''
    separators = ['.', '!', '?']
    
    pattern = re.compile(
    r'.*?(?:mm|㎜)\s*[^.!?]*(?:이다|이며|정도이다|내외이다)?',
    re.IGNORECASE
    )
    m = pattern.search(text)
    if m:
        size_clause = m.group(0).strip()
        leftover = text[m.end():].lstrip(' ,.;:').strip()
        return size_clause, leftover
    
    indices = [text.find(sep) for sep in separators if text.find(sep) != -1]
    if not indices:
        return text, ''
    split_idx = min(indices)
    size_clause = text[:split_idx + 1]
    leftover = text[split_idx + 1:]
    return size_clause.strip(), leftover.strip()


def _heuristic_split_ecology(text: str) -> dict:
    """
    라벨(서식지:, 먹이:, ...)이 없는 생태적특징 텍스트를
    서식지/먹이습성/행동습성/국내분포/국외분포로 대충 나눠주는 휴리스틱.
    """
    result = {
        COL_ECO_HABITAT: "",
        COL_ECO_DIET: "",
        COL_ECO_BEHAVIOR: "",
        COL_ECO_DOMESTIC: "",
        COL_ECO_OVERSEAS: "",
    }

    if _is_empty(text):
        return result

    s = str(text).strip()
    # 문장 단위로 대충 나누기 (.?! 기준 + 줄바꿈)
    sentences = re.split(r"[\.!?]\s*|\n+", s)
    sentences = [sent.strip() for sent in sentences if sent.strip()]

    # 키워드 세트 정의 (필요하면 계속 추가 가능)
    habitat_keywords = [
        "하천", "계곡", "강", "하구", "호수", "연못", "바다", "연안", "해안",
        "산지", "산림", "숲", "초지", "논", "밭", "농경지", "도심", "도시",
        "습지", "저수지", "수역", "벌채목", "나무껍질 밑", "껍질 밑",
        "에서 발견", "에서 서식", "에서 산", "에서 생활"
    ]

    diet_keywords = [
        "먹는다", "먹이", "섭취", "포식", "잡아먹", "흡즙", "빨아먹", "유기물",
        "곰팡이", "목재", "잎", "씨앗", "과일", "곤충을 잡아먹", "식성"
    ]

    behavior_keywords = [
        "행동", "활동", "날아", "비행", "기어다니", "숨는다", "은신",
        "산란", "우화", "번식", "밤에", "야행성", "주행성", "관찰된다", "관찰 시기"
    ]

    # 국내·국외 분포 판단용
    korea_keywords = ["한국", "남한", "북한", "한반도", "제주", "대한민국"]
    foreign_keywords = [
        "일본", "대만", "중국", "러시아", "유럽", "북미",
        "인도", "인디아", "인도차이나", "부마", "동남아", "아시아", "아프리카", "오세아니아"
    ]

    domestic_sentences = []
    overseas_sentences = []
    habitat_sentences = []
    diet_sentences = []
    behavior_sentences = []

    for sent in sentences:
        lowered = sent.replace(" ", "")

        # 1) 분포 관련 문장
        if "분포" in sent or "분포한다" in sent:
            has_korea = any(k in sent for k in korea_keywords)
            has_foreign = any(f in sent for f in foreign_keywords)
            if has_korea:
                domestic_sentences.append(sent)
            if has_foreign or not has_korea:
                overseas_sentences.append(sent)
            continue

        # 2) 국내/국외 키워드만 있는 경우도 분포로 처리
        has_korea_only = any(k in sent for k in korea_keywords)
        has_foreign_only = any(f in sent for f in foreign_keywords)
        if has_korea_only and not has_foreign_only:
            domestic_sentences.append(sent)
            continue
        if has_foreign_only:
            overseas_sentences.append(sent)
            continue

        # 3) 서식지 후보
        if any(kw in sent for kw in habitat_keywords):
            habitat_sentences.append(sent)
            continue

        # 4) 먹이/식성
        if any(kw in sent for kw in diet_keywords):
            diet_sentences.append(sent)
            continue

        # 5) 행동/관찰 시기
        if any(kw in sent for kw in behavior_keywords):
            behavior_sentences.append(sent)
            continue

        # 6) 여기에 안 걸리면 → 행동으로 넣는 것도 한 방법
        behavior_sentences.append(sent)

    # 결과 합치기
    if habitat_sentences:
        result[COL_ECO_HABITAT] = " ".join(habitat_sentences)
    if diet_sentences:
        result[COL_ECO_DIET] = " ".join(diet_sentences)
    if behavior_sentences:
        result[COL_ECO_BEHAVIOR] = " ".join(behavior_sentences)
    if domestic_sentences:
        result[COL_ECO_DOMESTIC] = " ".join(domestic_sentences)
    if overseas_sentences:
        result[COL_ECO_OVERSEAS] = " ".join(overseas_sentences)

    return result

def convert_to_naver(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터를 네이버백과사전 형식으로 변환합니다.
    """

    print("\n===== [NAVER] convert_to_naver 시작 =====")
    print(f"[NAVER] 입력 df shape: {df.shape}")
    print(f"[NAVER] 입력 df columns: {list(df.columns)}")

    try:
        normalized_columns = {_normalize_identifier(col): col for col in df.columns}
        print(f"[NAVER] 정규화된 컬럼 키: {list(normalized_columns.keys())}")

        # 오타 체크용: 실제 원본 컬럼에 이런 애들이 있는지 한번 찍어봄
        for key in ['분류 세기 라틴명', '분류 세기 명', '분류체계라틴명', '분류체계명', 'scnm', 'cnnm']:
            norm = _normalize_identifier(key)
            print(f"[NAVER] 찾고 싶은 컬럼 '{key}' -> 정규화 '{norm}', 실제 매핑: {normalized_columns.get(norm)}")

        direct_mapping = {
            'id': COL_ID,
            '분류체계라틴명': COL_LATIN,
            '분류체계명': COL_KOREAN,
            '분류군': COL_GROUP,
            'scnm': COL_SCIENTIFIC,
            'cnnm': COL_COMMON,
            '업데이트유무': COL_UPDATE,
            '생태적 특징': COL_ECO_RAW,
            '일반적 특징': COL_GENERAL_RAW,
            '천년기념물': COL_PROTECTED_NATURAL,   # ← 여기 '천연기념물' 오타 아닌지도 나중에 한번 확인!
            '멸종위기종': COL_ENDANGERED,
            '보호식물명': COL_PROTECTED_PLANT
        }

        print("[NAVER] _apply_direct_mapping 호출")
        result_df = _apply_direct_mapping(df, normalized_columns, direct_mapping)
        print(f"[NAVER] direct mapping 이후 result_df.columns: {list(result_df.columns)}")

        # 보호지정 컬럼 정리
        for designation_col in [COL_PROTECTED_NATURAL, COL_ENDANGERED, COL_PROTECTED_PLANT]:
            if designation_col in result_df:
                print(f"[NAVER] 지정 컬럼 정리: {designation_col}")
                result_df[designation_col] = result_df[designation_col].apply(_designation_label)

        # 복합 컬럼 분리 정의
        ecology_sections = {
            COL_ECO_HABITAT: ['서식지', '서식 환경', '서식처'],
            COL_ECO_DIET: ['먹이습성', '먹이 습성', '식성'],
            COL_ECO_BEHAVIOR: ['행동습성', '행동 습성', '주요 습성', '관찰 시기'],  # ← 여기!
            COL_ECO_DOMESTIC: ['국내분포', '국내 분포'],
            COL_ECO_OVERSEAS: ['국외분포', '국외 분포']
        }
        general_sections = {
            COL_GENERAL_SIZE: ['크기'],
            COL_GENERAL_TRAIT: ['주요형질', '주요 형질']
        }

        print("[NAVER] _extract_section_series(ecology) 호출")
        ecology_series = _extract_section_series(df, normalized_columns, SRC_ECO_FEATURE, ecology_sections)
        print(f"[NAVER] ecology_series keys: {list(ecology_series.keys())}")

        print("[NAVER] _extract_section_series(general) 호출")
        general_series = _extract_section_series(df, normalized_columns, SRC_GENERAL_FEATURE, general_sections)
        print(f"[NAVER] general_series keys: {list(general_series.keys())}")

        for target_col, series in ecology_series.items():
            print(f"[NAVER] ecology 시리즈 병합: {target_col}")
            result_df[target_col] = series

        for target_col, series in general_series.items():
            print(f"[NAVER] general 시리즈 병합: {target_col}")
            result_df[target_col] = series

        # 개별 컬럼 fallback
        fallback_sources = {
            '서식지':        COL_ECO_HABITAT,
            '먹이습성':      COL_ECO_DIET,
            '행동습성':      COL_ECO_BEHAVIOR,
            '국내분포':      COL_ECO_DOMESTIC,
            '국외분포':      COL_ECO_OVERSEAS,
            '크기':          COL_GENERAL_SIZE,
            '주요형질':      COL_GENERAL_TRAIT
        }

        print("[NAVER] _fill_fallback_values 호출")
        _fill_fallback_values(result_df, df, normalized_columns, fallback_sources)

        print("[NAVER] _apply_general_text_heuristics 호출")
        _apply_general_text_heuristics(result_df)
        # 1) 생태 raw가 비어 있는 경우: 서식지/먹이/행동/분포를 합쳐서 생성
        if COL_ECO_RAW in result_df:
            eco_all_empty = result_df[COL_ECO_RAW].map(_is_empty).all()
        else:
            eco_all_empty = True
            result_df[COL_ECO_RAW] = np.nan

        if eco_all_empty:
            def _build_eco_raw(row):
                parts = []
                if not _is_empty(row.get(COL_ECO_HABITAT, None)):
                    parts.append(f"서식지: {row[COL_ECO_HABITAT]}")
                if not _is_empty(row.get(COL_ECO_DIET, None)):
                    parts.append(f"먹이습성: {row[COL_ECO_DIET]}")
                if not _is_empty(row.get(COL_ECO_BEHAVIOR, None)):
                    parts.append(f"행동습성: {row[COL_ECO_BEHAVIOR]}")
                if not _is_empty(row.get(COL_ECO_DOMESTIC, None)):
                    parts.append(f"국내분포: {row[COL_ECO_DOMESTIC]}")
                if not _is_empty(row.get(COL_ECO_OVERSEAS, None)):
                    parts.append(f"국외분포: {row[COL_ECO_OVERSEAS]}")
                return " || ".join(parts) if parts else np.nan

            print("[NAVER] COL_ECO_RAW 비어있어 서식지/먹이/행동/분포에서 재구성")
            result_df[COL_ECO_RAW] = result_df.apply(_build_eco_raw, axis=1)

        # 2) 일반 raw가 비어 있는 경우: 크기 + 주요형질을 합쳐서 생성
        if COL_GENERAL_RAW in result_df:
            gen_all_empty = result_df[COL_GENERAL_RAW].map(_is_empty).all()
        else:
            gen_all_empty = True
            result_df[COL_GENERAL_RAW] = np.nan

        if gen_all_empty:
            def _build_general_raw(row):
                parts = []
                if not _is_empty(row.get(COL_GENERAL_SIZE, None)):
                    parts.append(row[COL_GENERAL_SIZE])
                if not _is_empty(row.get(COL_GENERAL_TRAIT, None)):
                    parts.append(row[COL_GENERAL_TRAIT])
                return " ".join(parts).strip() if parts else np.nan

            print("[NAVER] COL_GENERAL_RAW 비어있어 크기/주요형질에서 재구성")
            result_df[COL_GENERAL_RAW] = result_df.apply(_build_general_raw, axis=1)

        # 최종 컬럼 순서
        final_columns = [
            COL_ID,
            COL_LATIN,
            COL_KOREAN,
            COL_GROUP,
            COL_SCIENTIFIC,
            COL_COMMON,
            COL_UPDATE,
            COL_ECO_RAW,
            COL_ECO_HABITAT,
            COL_ECO_DIET,
            COL_ECO_BEHAVIOR,
            COL_ECO_DOMESTIC,
            COL_ECO_OVERSEAS,
            COL_GENERAL_RAW,
            COL_GENERAL_SIZE,
            COL_GENERAL_TRAIT,
            COL_PROTECTED_NATURAL,
            COL_ENDANGERED,
            COL_PROTECTED_PLANT
        ]

        print(f"[NAVER] final_columns: {final_columns}")

        # 없는 컬럼은 NaN으로 채우기
        for col in final_columns:
            if col not in result_df.columns:
                print(f"[NAVER] 누락된 컬럼 생성: {col}")
                result_df[col] = np.nan

        result_df = result_df[final_columns]
        print(f"[NAVER] 최종 result_df shape: {result_df.shape}")
        print(f"[NAVER] 최종 result_df columns: {list(result_df.columns)}")
        print("===== [NAVER] convert_to_naver 종료 (정상) =====\n")

        return result_df

    except Exception as e:
        print("===== [NAVER] convert_to_naver ERROR 발생 =====")
        print(f"[NAVER] 에러 메시지: {e}")
        print("[NAVER] traceback:")
        print(traceback.format_exc())
        print("===== [NAVER] convert_to_naver ERROR 끝 =====\n")
        # Streamlit에서 보이도록 다시 raise
        raise


    

def convert_to_bioone(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터를 바이오원(BioOne) 형식으로 변환합니다.
    바이오원 데이터베이스에 적합한 형식으로 데이터를 재구성합니다.
    """
    # 바이오원 형식 필드 (예시)
    bioone_columns = [
        'TaxonID',
        'ScientificName',
        'Author',
        'Year',
        'Kingdom',
        'Phylum',
        'Class',
        'Order',
        'Family',
        'Genus',
        'Species',
        'Subspecies',
        'CommonName',
        'Distribution',
        'Habitat',
        'ConservationStatus',
        'Reference',
        'DOI'
    ]
    
    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame()
    
    # 기존 데이터의 컬럼을 바이오원 형식에 매핑
    column_mapping = {}
    
    # 기본 매핑 시도
    mapping_keywords = {
        'ScientificName': ['scientific', '학명', 'scientificName'],
        'Author': ['author', '저자', '작성자'],
        'Year': ['year', '연도', '년도'],
        'Kingdom': ['kingdom', '계'],
        'Phylum': ['phylum', '문'],
        'Class': ['class', '강'],
        'Order': ['order', '목'],
        'Family': ['family', '과'],
        'Genus': ['genus', '속'],
        'Species': ['species', '종'],
        'CommonName': ['common', '한글명', '영문명'],
        'Distribution': ['distribution', '분포', '분포지역'],
        'Habitat': ['habitat', '서식지', '서식'],
        'ConservationStatus': ['conservation', '보전', '멸종위기']
    }
    
    for bioone_col, keywords in mapping_keywords.items():
        for orig_col in df.columns:
            if any(keyword.lower() in orig_col.lower() for keyword in keywords):
                column_mapping[bioone_col] = orig_col
                break
    
    # 매핑된 컬럼 복사
    for bioone_col in bioone_columns:
        if bioone_col in column_mapping:
            result_df[bioone_col] = df[column_mapping[bioone_col]]
        else:
            result_df[bioone_col] = np.nan
    
    return result_df

