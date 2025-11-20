import pandas as pd
import numpy as np
import re

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
SIZE_KEYWORDS = ['크기', '몸길이', '체장', '길이']


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
    return [segment.strip() for segment in re.split(r'\n|\|\|', normalized_text) if segment.strip()]


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
    lookup = _build_label_lookup(section_variants)
    num_rows = len(df)
    values = {col: [np.nan] * num_rows for col in section_variants}
    source_col = normalized_columns.get(source_key)
    
    if source_col:
        series = df[source_col].fillna('')
        for idx, raw_text in enumerate(series):
            parsed = _parse_section_text(raw_text, lookup, section_variants.keys())
            for target_col in section_variants:
                values[target_col][idx] = parsed[target_col]
    
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
    if COL_GENERAL_RAW not in result_df:
        return
    
    sentence_splitter = re.compile(r'(?<=[.!?])\s*|\n+')
    mm_pattern = re.compile(r'\bmm\b', re.IGNORECASE)
    
    for idx, raw_text in result_df[COL_GENERAL_RAW].items():
        _update_general_row(result_df, idx, raw_text, sentence_splitter, mm_pattern)


def _update_general_row(result_df, idx, raw_text, sentence_splitter, mm_pattern):
    if _is_empty(raw_text):
        return
    
    size_value = result_df.at[idx, COL_GENERAL_SIZE] if COL_GENERAL_SIZE in result_df else None
    trait_value = result_df.at[idx, COL_GENERAL_TRAIT] if COL_GENERAL_TRAIT in result_df else None
    
    if not _is_empty(size_value) and not _is_empty(trait_value):
        return
    
    size_candidate, trait_candidate = _derive_general_values(raw_text, sentence_splitter, mm_pattern)
    
    if _is_empty(size_value) and size_candidate:
        result_df.at[idx, COL_GENERAL_SIZE] = size_candidate
    
    if _is_empty(trait_value) and trait_candidate:
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
    indices = [text.find(sep) for sep in separators if text.find(sep) != -1]
    if not indices:
        return text, ''
    split_idx = min(indices)
    size_clause = text[:split_idx + 1]
    leftover = text[split_idx + 1:]
    return size_clause.strip(), leftover.strip()

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


def convert_to_naver(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터를 네이버백과 전처리 규칙에 맞춰 변환합니다.
    제공된 매핑 표를 기준으로 단순 매핑 및 복수 컬럼 분리(생태적특징, 일반적 특징)를 수행합니다.
    """
    normalized_columns = {_normalize_identifier(col): col for col in df.columns}
    
    # 단순 매핑 컬럼
    direct_mapping = {
        'id': COL_ID,
        '분류체계라틴명': COL_LATIN,
        '분류체계명': COL_KOREAN,
        '분류군': COL_GROUP,
        'scnm': COL_SCIENTIFIC,
        'cnnm': COL_COMMON,
        '업데이트유무': COL_UPDATE,
        SRC_ECO_FEATURE: COL_ECO_RAW,
        SRC_GENERAL_FEATURE: COL_GENERAL_RAW,
        '천년기념물': COL_PROTECTED_NATURAL,
        '멸종위기종': COL_ENDANGERED,
        '보호식물명': COL_PROTECTED_PLANT
    }
    
    result_df = _apply_direct_mapping(df, normalized_columns, direct_mapping)
    for designation_col in [COL_PROTECTED_NATURAL, COL_ENDANGERED, COL_PROTECTED_PLANT]:
        if designation_col in result_df:
            result_df[designation_col] = result_df[designation_col].apply(_designation_label)
    
    # 복합 컬럼 분리 정의
    ecology_sections = {
        COL_ECO_HABITAT: ['서식지', '서식 환경', '서식처'],
        COL_ECO_DIET: ['먹이습성', '먹이 습성', '식성'],
        COL_ECO_BEHAVIOR: ['행동습성', '행동 습성'],
        COL_ECO_DOMESTIC: ['국내분포', '국내 분포'],
        COL_ECO_OVERSEAS: ['국외분포', '국외 분포']
    }
    general_sections = {
        COL_GENERAL_SIZE: ['크기'],
        COL_GENERAL_TRAIT: ['주요형질', '주요 형질']
    }
    
    ecology_series = _extract_section_series(df, normalized_columns, SRC_ECO_FEATURE, ecology_sections)
    general_series = _extract_section_series(df, normalized_columns, SRC_GENERAL_FEATURE, general_sections)
    
    for target_col, series in ecology_series.items():
        result_df[target_col] = series
    for target_col, series in general_series.items():
        result_df[target_col] = series
    
    # 개별 컬럼이 존재할 경우(서식지, 크기 등) 파싱 결과의 결측치를 보완
    fallback_sources = {
        '서식지': COL_ECO_HABITAT,
        '먹이습성': COL_ECO_DIET,
        '행동습성': COL_ECO_BEHAVIOR,
        '국내분포': COL_ECO_DOMESTIC,
        '국외분포': COL_ECO_OVERSEAS,
        '크기': COL_GENERAL_SIZE,
        '주요형질': COL_GENERAL_TRAIT
    }
    
    _fill_fallback_values(result_df, df, normalized_columns, fallback_sources)
    _apply_general_text_heuristics(result_df)
    
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
    
    for col in final_columns:
        if col not in result_df.columns:
            result_df[col] = np.nan
    
    result_df = result_df[final_columns]
    
    return result_df


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

