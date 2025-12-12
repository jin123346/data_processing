import pandas as pd
import numpy as np
import re
<<<<<<< HEAD
import traceback


=======
>>>>>>> dbd69d0e4b057bff0949074d12d7ae117b7500cd

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
    """
    텍스트를 의미 단위(줄)로 분리합니다. 
    HTML 태그(<br>)와 특수 구분자(||)를 처리합니다.
    """
    if not text_str:
        return []
        
    normalized_text = str(text_str)
    # HTML 태그 및 특수 문자 전처리
    normalized_text = normalized_text.replace('<br>', '\n').replace('<br/>', '\n')
    normalized_text = normalized_text.replace('||', '\n')
    normalized_text = normalized_text.replace('：', ':') # 전각 콜론 처리
    
    # 문장 종결 부호 뒤에 줄바꿈이 없다면 강제로 줄바꿈 추가 (비구조화 텍스트 처리용)
    # 예: "발견된다. 유기물을" -> "발견된다.\n유기물을"
    normalized_text = re.sub(r'(?<=[.!?])\s+(?=[가-힣])', '\n', normalized_text)

    return [segment.strip() for segment in re.split(r'\n', normalized_text) if segment.strip()]



def _heuristic_parse_ecology(text_segments):
    """
    라벨이 없는 문장들을 키워드 기반으로 생태 정보로 분류합니다.
    """
    parsed = {
        '서식지': [],
        '먹이습성': [],
        '행동습성': [],
        '국내분포': [],
        '국외분포': []
    }
    
    # 분류 키워드 사전
    keywords = {
        '서식지': ['서식', '발견', '계곡', '하천', '산지', '풀밭', '낙엽', '물속', '바닥', '기주'],
        '먹이습성': ['먹는', '먹이', '식성', '섭취', '포식', '흡즙', '가해'],
        '행동습성': ['활동', '비행', '주행', '월동', '산란', '우화', '짓고', '무리', '단독'],
        '국내분포': ['국내', '경기도', '강원', '제주', '충청', '전라', '경상', '북한', '전국'],
        '국외분포': ['국외', '일본', '중국', '러시아', '유럽', '미국', '동남아', '전세계']
    }

    for segment in text_segments:
        matched = False
        
        # 1. 분포 정보 우선 확인 (지명 등 고유명사가 많으므로)
        if any(k in segment for k in keywords['국외분포']):
            parsed['국외분포'].append(segment)
            continue
        if any(k in segment for k in keywords['국내분포']):
            parsed['국내분포'].append(segment)
            continue
            
        # 2. 나머지 생태 정보 확인
        for category in ['먹이습성', '행동습성', '서식지']:
            if any(k in segment for k in keywords[category]):
                parsed[category].append(segment)
                matched = True
                break # 하나의 문장은 하나의 카테고리로 (우선순위: 먹이 > 행동 > 서식)
        
        # 매칭되지 않은 문장은 내용에 따라 '서식지'나 '행동습성'으로 보낼 수 있음 (기본값: 서식지)
        if not matched:
            parsed['서식지'].append(segment)

    # 리스트를 문자열로 합치기
    return {k: ' '.join(v) if v else np.nan for k, v in parsed.items()}

# def _split_sections(text_str: str):
#     normalized_text = text_str.replace('\r', '\n')
#     normalized_text = normalized_text.replace('||', '\n')
#     normalized_text = normalized_text.replace('：', ':')
#     return [segment.strip() for segment in re.split(r'\n|\|\|', normalized_text) if segment.strip()]

def _heuristic_parse_general(text_segments):
    """
    문장들을 분석하여 크기 정보와 주요 형질로 분리합니다.
    """
    size_texts = []
    trait_texts = []
    
    # 크기 관련 정규식 (숫자 + 공백(선택) + 단위)
    size_pattern = re.compile(r'\d+(\.\d+)?\s*(mm|cm|m|밀리미터|센티미터|미터)', re.IGNORECASE)
    size_keywords = ['크기', '체장', '몸길이', '길이']

    for segment in text_segments:
        is_size = False
        
        # 1. 명시적 키워드가 있거나
        if any(segment.startswith(k) for k in size_keywords):
            is_size = True
        # 2. 숫자+단위 패턴이 포함된 문장이라면
        elif size_pattern.search(segment):
            is_size = True
            
        if is_size:
            # "크기는" 같은 불필요한 접두어 제거 시도 (선택사항)
            clean_segment = segment
            for k in size_keywords:
                 if clean_segment.startswith(k):
                     clean_segment = clean_segment.replace(k, '', 1).lstrip(' 는은이가:-')
            # 원래 문장을 유지할지, 정제된 문장을 넣을지 결정 (여기선 원래 문장 유지하되, 필요시 clean_segment 사용)
            size_texts.append(segment)
        else:
            trait_texts.append(segment)
            
    return {
        '크기': ' '.join(size_texts) if size_texts else np.nan,
        '주요형질': ' '.join(trait_texts) if trait_texts else np.nan
    }

def _resolve_label_value(piece: str, label_lookup):
    """
    주어진 텍스트 조각에서 라벨과 값을 분리합니다.
    (이전 답변에서 제시된 코드를 사용합니다.)
    """
    piece = piece.strip()
    
    # 1. 콜론(:)이 명시적으로 있는 경우 (가장 확실한 케이스)
    if ':' in piece:
        label_part, value_part = piece.split(':', 1)
        # 콜론으로 분리 후, 값 부분의 앞쪽 공백과 불필요한 문자(이전 라벨에서 남은 잔여 문자) 제거
        value_part = value_part.lstrip(LABEL_SUFFIX_CHARS) 
        return label_part.strip(), value_part.strip()
    
    # 2. 콜론(:)이 없는 경우 (공백, 기타 문자로 라벨이 끝난 경우)
    for _, (_, raw_label) in label_lookup.items():
        raw_label_clean = raw_label.strip()
        
        # 라벨 접두사 후보군 정의
        prefixes = [
            raw_label_clean + ' :',  # 예: '서식지 :'
            raw_label_clean + ':',   # 예: '서식지:'
            raw_label_clean,         # 예: '서식지'
            raw_label_clean.replace(' ', '') # 예: '서식지' (공백 없는 경우)
        ]
        
        for prefix in prefixes:
            if piece.startswith(prefix):
                # 라벨 길이만큼 자른 후, 뒤에 붙은 불필요한 문자(공백, :, -, 는/은 등)를 강력하게 제거
                value_part = piece[len(prefix):].lstrip(LABEL_SUFFIX_CHARS)
                return raw_label_clean, value_part
                
    return None, None

# def _resolve_label_value(piece: str, label_lookup):
#     if ':' in piece:
#         label_part, value_part = piece.split(':', 1)
#         return label_part, value_part
    
#     for _, (_, raw_label) in label_lookup.items():
#         if piece.startswith(raw_label):
#             value_part = piece[len(raw_label):].lstrip(LABEL_SUFFIX_CHARS)
#             return raw_label, value_part
#         if piece.startswith(raw_label.replace(' ', '')):
#             value_part = piece[len(raw_label.replace(' ', '')):].lstrip(LABEL_SUFFIX_CHARS)
#             return raw_label, value_part
#     return None, None


def _parse_section_text(text, label_lookup, target_columns, section_type='ecology'):
    """
    통합 파싱 함수: 라벨 파싱 시도 -> 실패 시 휴리스틱 파싱 시도
    section_type: 'ecology' 또는 'general'
    """
    parsed = {target: np.nan for target in target_columns}
    
    if pd.isna(text):
        return parsed
    text_str = str(text).strip()
    if not text_str:
        return parsed
    
    segments = _split_sections(text_str)
    
    # 1단계: 명시적 라벨(예: "서식지 :")이 하나라도 있는지 확인
    has_label = False
    temp_parsed = {target: [] for target in target_columns} # 중복 등장을 위해 리스트로 임시 저장

    for piece in segments:
        label_part, value_part = _resolve_label_value(piece, label_lookup)
        if label_part and label_part in label_lookup:
            target_col, _ = label_lookup[label_part]
            if target_col in temp_parsed:
                has_label = True
                if value_part:
                    temp_parsed[target_col].append(value_part.strip())
    
    # 2단계: 라벨 파싱에 성공했다면 그 결과 반환
    if has_label:
        for k, v_list in temp_parsed.items():
            if v_list:
                parsed[k] = ' '.join(v_list)
        return parsed
    
    # 3단계: 라벨이 없다면 휴리스틱(문맥 추론) 적용
    if section_type == 'ecology':
        mapping = {
            '서식지': COL_ECO_HABITAT,
            '먹이습성': COL_ECO_DIET,
            '행동습성': COL_ECO_BEHAVIOR,
            '국내분포': COL_ECO_DOMESTIC,
            '국외분포': COL_ECO_OVERSEAS
        }
        # 휴리스틱 결과 가져오기
        heuristic_result = _heuristic_parse_ecology(segments)
        
        # 결과 매핑
        for key, val in heuristic_result.items():
            # 해당 키가 타겟 컬럼 리스트에 있는 경우에만 할당
            # (target_columns는 실제 컬럼명 리스트이므로, 매핑 테이블을 통해 연결)
            target_col_name = mapping.get(key)
            if target_col_name in parsed:
                parsed[target_col_name] = val
                
    elif section_type == 'general':
        heuristic_result = _heuristic_parse_general(segments)
        # 일반적 특징 매핑
        if COL_GENERAL_SIZE in parsed:
            parsed[COL_GENERAL_SIZE] = heuristic_result['크기']
        if COL_GENERAL_TRAIT in parsed:
            parsed[COL_GENERAL_TRAIT] = heuristic_result['주요형질']
            
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

def convert_to_gbif(df: pd.DataFrame, basis_of_record: str = None) -> pd.DataFrame:
    """
    데이터를 GBIF 형식으로 변환합니다.
    한국어 컬럼명을 GBIF 표준 필드에 맞게 매핑합니다.
    
    Args:
        df: 변환할 데이터프레임
        basis_of_record: basisOfRecord 필드에 설정할 값 (HumanObservation 또는 PreservedSpecimen)
                        None이면 기존 데이터에서 매핑을 시도합니다.
    """
    # 컬럼명 정규화 (공백, 특수문자 제거 후 소문자 변환)
    print("💡 convert_to_gbif: 입력 df 행 수 =", len(df)) 
    normalized_columns = {_normalize_identifier(col): col for col in df.columns}
    
    # 디버깅: 실제 컬럼명 출력
    print("=== 컬럼명 디버깅 ===")
    print(f"원본 컬럼명: {list(df.columns)}")
    print(f"정규화된 컬럼명: {list(normalized_columns.keys())}")
    
    # 데이터베이스번호 컬럼 찾기 (여러 변형 시도)
    db_number_col = None
    db_number_variants = [
        '데이터베이스번호',
        '데이터베이스번호기관코드분류코드',  # 괄호 내용 포함
        '데이터베이스',  # 부분 매칭
    ]
    
    for variant in db_number_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            db_number_col = normalized_columns[normalized_variant]
            print(f"✅ 데이터베이스번호 컬럼 찾음: '{db_number_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if db_number_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '데이터베이스번호' in norm_col or '데이터베이스' in norm_col:
                db_number_col = orig_col
                print(f"✅ 데이터베이스번호 컬럼 찾음 (부분 매칭): '{db_number_col}'")
                break
    
    if db_number_col:
        print(f"데이터베이스번호 샘플 값: {df[db_number_col].head(3).tolist()}")
    else:
        print("⚠️ 데이터베이스번호 컬럼을 찾을 수 없습니다.")
        print(f"사용 가능한 컬럼명: {list(df.columns)}")
    
    # 관찰일자 컬럼 찾기 (eventDate용)
    event_date_col = None
    event_date_variants = [
        '관찰일자',
        '관찰월일',
        '관찰일',
    ]
    
    for variant in event_date_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            event_date_col = normalized_columns[normalized_variant]
            print(f"✅ 관찰일자 컬럼 찾음: '{event_date_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if event_date_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '관찰일자' in norm_col or '관찰월일' in norm_col or '관찰일' in norm_col:
                event_date_col = orig_col
                print(f"✅ 관찰일자 컬럼 찾음 (부분 매칭): '{event_date_col}'")
                break
    
    if event_date_col:
        print(f"관찰일자 샘플 값: {df[event_date_col].head(3).tolist()}")
    else:
        print("⚠️ 관찰일자 컬럼을 찾을 수 없습니다.")
    
    # 기관코드 컬럼 찾기 (institutionCode용)
    institution_code_col = None
    institution_code_variants = [
        '기관코드',
        '기관코드기관명입력시자동생성',  # 괄호 내용 포함
        '기관',
    ]
    
    for variant in institution_code_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            institution_code_col = normalized_columns[normalized_variant]
            print(f"✅ 기관코드 컬럼 찾음: '{institution_code_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기 (기관코드만 정확히 매칭)
    if institution_code_col is None:
        for norm_col, orig_col in normalized_columns.items():
            # '기관코드'가 정확히 포함되어야 함 (사업명 등 다른 컬럼 제외)
            if '기관코드' in norm_col:
                institution_code_col = orig_col
                print(f"✅ 기관코드 컬럼 찾음 (부분 매칭): '{institution_code_col}'")
                break
    
    if institution_code_col:
        print(f"기관코드 샘플 값: {df[institution_code_col].head(3).tolist()}")
    else:
        print("⚠️ 기관코드 컬럼을 찾을 수 없습니다.")
    
    # 학명 컬럼 찾기 (scientificName용)
    scientific_name_col = None
    scientific_name_variants = [
        '학명',
        '학명국명입력시자동생성',  # 괄호 내용 포함
    ]
    
    for variant in scientific_name_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            scientific_name_col = normalized_columns[normalized_variant]
            print(f"✅ 학명 컬럼 찾음: '{scientific_name_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기 (학명만 정확히 매칭)
    if scientific_name_col is None:
        for norm_col, orig_col in normalized_columns.items():
            # '학명'이 정확히 포함되어야 함
            if '학명' in norm_col:
                scientific_name_col = orig_col
                print(f"✅ 학명 컬럼 찾음 (부분 매칭): '{scientific_name_col}'")
                break
    
    if scientific_name_col:
        print(f"학명 샘플 값: {df[scientific_name_col].head(3).tolist()}")
    else:
        print("⚠️ 학명 컬럼을 찾을 수 없습니다.")
    
    # 위도 컬럼 찾기 (decimalLatitude용)
    latitude_col = None
    latitude_variants = [
        '위도',
        '위도소수점으로입력',  # 괄호 내용 포함
    ]
    
    for variant in latitude_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            latitude_col = normalized_columns[normalized_variant]
            print(f"✅ 위도 컬럼 찾음: '{latitude_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기 (위도만 정확히 매칭)
    if latitude_col is None:
        for norm_col, orig_col in normalized_columns.items():
            # '위도'가 정확히 포함되어야 함
            if '위도' in norm_col:
                latitude_col = orig_col
                print(f"✅ 위도 컬럼 찾음 (부분 매칭): '{latitude_col}'")
                break
    
    if latitude_col:
        print(f"위도 샘플 값: {df[latitude_col].head(3).tolist()}")
    else:
        print("⚠️ 위도 컬럼을 찾을 수 없습니다.")
    
    # 경도 컬럼 찾기 (decimalLongitude용)
    longitude_col = None
    longitude_variants = [
        '경도',
        '경도소수점으로입력',  # 괄호 내용 포함
    ]
    
    for variant in longitude_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            longitude_col = normalized_columns[normalized_variant]
            print(f"✅ 경도 컬럼 찾음: '{longitude_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기 (경도만 정확히 매칭)
    if longitude_col is None:
        for norm_col, orig_col in normalized_columns.items():
            # '경도'가 정확히 포함되어야 함
            if '경도' in norm_col:
                longitude_col = orig_col
                print(f"✅ 경도 컬럼 찾음 (부분 매칭): '{longitude_col}'")
                break
    
    if longitude_col:
        print(f"경도 샘플 값: {df[longitude_col].head(3).tolist()}")
    else:
        print("⚠️ 경도 컬럼을 찾을 수 없습니다.")
    
    # 국가영문명 컬럼 찾기 (countryCode용)
    country_name_col = None
    country_name_variants = [
        '국가영문명',
        '국가코드',
    ]
    
    for variant in country_name_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            country_name_col = normalized_columns[normalized_variant]
            print(f"✅ 국가영문명 컬럼 찾음: '{country_name_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if country_name_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '국가영문명' in norm_col or '국가코드' in norm_col:
                country_name_col = orig_col
                print(f"✅ 국가영문명 컬럼 찾음 (부분 매칭): '{country_name_col}'")
                break
    
    if country_name_col:
        print(f"국가영문명 샘플 값: {df[country_name_col].head(3).tolist()}")
    else:
        print("⚠️ 국가영문명 컬럼을 찾을 수 없습니다.")
    
    # 동정년월일 컬럼 찾기 (dateIdentified용)
    date_identified_col = None
    date_identified_variants = [
        '동정년월일',
        '동정일자',
        '동정일',
    ]
    
    for variant in date_identified_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            date_identified_col = normalized_columns[normalized_variant]
            print(f"✅ 동정년월일 컬럼 찾음: '{date_identified_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if date_identified_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '동정년월일' in norm_col or '동정일자' in norm_col or '동정일' in norm_col:
                date_identified_col = orig_col
                print(f"✅ 동정년월일 컬럼 찾음 (부분 매칭): '{date_identified_col}'")
                break
    
    if date_identified_col:
        print(f"동정년월일 샘플 값: {df[date_identified_col].head(3).tolist()}")
    else:
        print("⚠️ 동정년월일 컬럼을 찾을 수 없습니다.")
    
    # 동정자 영문 컬럼 찾기 (identifiedBy용)
    identified_by_col = None
    identified_by_variants = [
        '동정자영문',
        '동정자',
    ]
    
    for variant in identified_by_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            identified_by_col = normalized_columns[normalized_variant]
            print(f"✅ 동정자 영문 컬럼 찾음: '{identified_by_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if identified_by_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '동정자영문' in norm_col or '동정자' in norm_col:
                identified_by_col = orig_col
                print(f"✅ 동정자 영문 컬럼 찾음 (부분 매칭): '{identified_by_col}'")
                break
    
    if identified_by_col:
        print(f"동정자 영문 샘플 값: {df[identified_by_col].head(3).tolist()}")
    else:
        print("⚠️ 동정자 영문 컬럼을 찾을 수 없습니다.")
    
    # 관찰위치 시도 영문 컬럼 찾기 (stateProvince용)
    state_province_col = None
    state_province_variants = [
        '관찰위치시도영문',
        '시도영문',
    ]
    
    for variant in state_province_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            state_province_col = normalized_columns[normalized_variant]
            print(f"✅ 관찰위치 시도 영문 컬럼 찾음: '{state_province_col}' (정규화: '{normalized_variant}')")
            break
    
    if state_province_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '관찰위치시도영문' in norm_col or '시도영문' in norm_col:
                state_province_col = orig_col
                print(f"✅ 관찰위치 시도 영문 컬럼 찾음 (부분 매칭): '{state_province_col}'")
                break
    
    if state_province_col:
        print(f"관찰위치 시도 영문 샘플 값: {df[state_province_col].head(3).tolist()}")
    else:
        print("⚠️ 관찰위치 시도 영문 컬럼을 찾을 수 없습니다.")
    
    # 관찰 위치 시군구 영문 컬럼 찾기 (county용)
    county_col = None
    county_variants = [
        '관찰위치시군구영문',
        '시군구영문',
    ]
    
    for variant in county_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            county_col = normalized_columns[normalized_variant]
            print(f"✅ 관찰 위치 시군구 영문 컬럼 찾음: '{county_col}' (정규화: '{normalized_variant}')")
            break
    
    if county_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '관찰위치시군구영문' in norm_col or '시군구영문' in norm_col:
                county_col = orig_col
                print(f"✅ 관찰 위치 시군구 영문 컬럼 찾음 (부분 매칭): '{county_col}'")
                break
    
    if county_col:
        print(f"관찰 위치 시군구 영문 샘플 값: {df[county_col].head(3).tolist()}")
    else:
        print("⚠️ 관찰 위치 시군구 영문 컬럼을 찾을 수 없습니다.")
    
    # 관찰위치 읍면동 영문 컬럼 찾기 (locality용)
    locality_col = None
    locality_variants = [
        '관찰위치읍면동영문',
        '읍면동영문',
    ]
    
    for variant in locality_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            locality_col = normalized_columns[normalized_variant]
            print(f"✅ 관찰위치 읍면동 영문 컬럼 찾음: '{locality_col}' (정규화: '{normalized_variant}')")
            break
    
    if locality_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '관찰위치읍면동영문' in norm_col or '읍면동영문' in norm_col:
                locality_col = orig_col
                print(f"✅ 관찰위치 읍면동 영문 컬럼 찾음 (부분 매칭): '{locality_col}'")
                break
    
    if locality_col:
        print(f"관찰위치 읍면동 영문 샘플 값: {df[locality_col].head(3).tolist()}")
    else:
        print("⚠️ 관찰위치 읍면동 영문 컬럼을 찾을 수 없습니다.")
    
    # 관찰위치 상세 영문 컬럼 찾기 (verbatimLocality용)
    verbatim_locality_col = None
    verbatim_locality_variants = [
        '관찰위치상세영문',
        '상세영문',
    ]
    
    for variant in verbatim_locality_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            verbatim_locality_col = normalized_columns[normalized_variant]
            print(f"✅ 관찰위치 상세 영문 컬럼 찾음: '{verbatim_locality_col}' (정규화: '{normalized_variant}')")
            break
    
    if verbatim_locality_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '관찰위치상세영문' in norm_col or '상세영문' in norm_col:
                verbatim_locality_col = orig_col
                print(f"✅ 관찰위치 상세 영문 컬럼 찾음 (부분 매칭): '{verbatim_locality_col}'")
                break
    
    if verbatim_locality_col:
        print(f"관찰위치 상세 영문 샘플 값: {df[verbatim_locality_col].head(3).tolist()}")
    else:
        print("⚠️ 관찰위치 상세 영문 컬럼을 찾을 수 없습니다.")
    
    # 국명 컬럼 찾기 (vernacularName용)
    vernacular_name_col = None
    vernacular_name_variants = [
        '국명',
        '국명\n(잘라내서 붙이기 안됨\n복사해서 붙이기는 허용)'
    ]
    
    for variant in vernacular_name_variants:
        normalized_variant = _normalize_identifier(variant)
        if normalized_variant in normalized_columns:
            vernacular_name_col = normalized_columns[normalized_variant]
            print(f"✅ 국명 컬럼 찾음: '{vernacular_name_col}' (정규화: '{normalized_variant}')")
            break
    
    # 정규화된 컬럼명에서 부분 매칭으로도 찾기
    if vernacular_name_col is None:
        for norm_col, orig_col in normalized_columns.items():
            if '국명' in norm_col or '한글명' in norm_col:
                vernacular_name_col = orig_col
                print(f"✅ 국명 컬럼 찾음 (부분 매칭): '{vernacular_name_col}'")
                break
    
    # 컬럼명으로 찾지 못한 경우 I열(9번째 열, 인덱스 8)을 직접 참조
    if vernacular_name_col is None and len(df.columns) > 8:
        vernacular_name_col = df.columns[8]  # I열은 9번째 열 (인덱스 8)
        print(f"✅ 국명 컬럼을 I열에서 찾음: '{vernacular_name_col}' (인덱스 8)")
    
    if vernacular_name_col:
        print(f"국명 샘플 값: {df[vernacular_name_col].head(3).tolist()}")
    else:
        print("⚠️ 국명 컬럼을 찾을 수 없습니다.")
    
    # 한국어 컬럼명 -> GBIF 필드 매핑 규칙
    # 이미지의 매핑 표를 기준으로 작성
    korean_to_gbif_mapping = {
        # 데이터베이스번호 -> occurrenceID
        '데이터베이스번호': 'occurrenceID',
        # 엑셀 삽입후 표본/관찰 선택 부분 필 -> basisOfRecord
        '엑셀삽입후표본관찰선택부분필': 'basisOfRecord',
        '표본관찰선택': 'basisOfRecord',
        '표본관찰': 'basisOfRecord',
        # 관찰월일 -> eventDate
        '관찰월일': 'eventDate',
        '관찰일자': 'eventDate',
        # 기관코드 -> institutionCode
        '기관코드': 'institutionCode',
        # 학명 -> scientificName
        '학명': 'scientificName',
        # 분류코드 -> collectionCode
        '분류코드': 'collectionCode',
        # 위도 -> decimalLatitude
        '위도': 'decimalLatitude',
        # 경도 -> decimalLongitude
        '경도': 'decimalLongitude',
        # 국가영문명 -> countryCode
        '국가영문명': 'countryCode',
        '국가코드': 'countryCode',
        # 동정년월일 -> dateIdentified
        '동정년월일': 'dateIdentified',
        '동정일자': 'dateIdentified',
        # 동정자 영문 -> identifiedBy
        '동정자영문': 'identifiedBy',
        '동정자': 'identifiedBy',
        # 관찰위치 시도 영문 -> stateProvince
        '관찰위치시도영문': 'stateProvince',
        '시도영문': 'stateProvince',
        # 관찰 위치 시군구 영문 -> county
        '관찰위치시군구영문': 'county',
        '시군구영문': 'county',
        # 관찰위치 읍면동 영문 -> locality
        '관찰위치읍면동영문': 'locality',
        '읍면동영문': 'locality',
        # 관찰위치 상세 영문 -> verbatimLocality
        '관찰위치상세영문': 'verbatimLocality',
        '상세영문': 'verbatimLocality',
        # 데이터베이스번호 (두 번째) -> catalogNumber
        # 주의: occurrenceID와 동일한 소스이지만 다른 필드로 매핑
        # 데이터베이스번호2 또는 별도 컬럼이 있다면 사용, 없으면 occurrenceID와 동일 값 사용
        '데이터베이스번호2': 'catalogNumber',
        # 국명 -> vernacularName
        '국명': 'vernacularName',
        '한글명': 'vernacularName',
    }
    
    # GBIF 표준 필드 목록 (이미지의 매핑 표 순서대로)
    gbif_columns = [
        'occurrenceID',
        'basisOfRecord',
        'eventDate',
        'institutionCode',
        'scientificName',
        'collectionCode',
        'decimalLatitude',
        'decimalLongitude',
        'countryCode',
        'dateIdentified',
        'identifiedBy',
        'stateProvince',
        'county',
        'locality',
        'verbatimLocality',
        'catalogNumber',
        'vernacularName'
    ]
    
    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame(index=df.index)
    
    # 데이터베이스번호를 먼저 처리
    if db_number_col:
        result_df['occurrenceID'] = df[db_number_col]
        print(f"✅ occurrenceID 필드에 데이터 복사 완료: {len(result_df[result_df['occurrenceID'].notna()])}개 행")
    else:
        result_df['occurrenceID'] = np.nan
        print("⚠️ occurrenceID 필드가 비어있습니다.")
    
    # 관찰일자를 eventDate에 매핑 (날짜 형식만 추출하여 텍스트로 저장)
    if event_date_col:
        def extract_date_format(value):
            """날짜 형식(####-##-##)만 추출하여 YYYY-MM-DD 텍스트 형식으로 반환"""
            if pd.isna(value):
                return np.nan
            
            value_str = str(value).strip()
            
            # 이미 YYYY-MM-DD 형식인 경우
            if re.match(r'^\d{4}-\d{2}-\d{2}$', value_str):
                return value_str
            
            # 날짜 형식 추출 (YYYY-MM-DD 또는 YYYY/MM/DD 등)
            # 다양한 날짜 형식 패턴 시도
            date_patterns = [
                r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',  # YYYY-MM-DD, YYYY/MM/DD
                r'(\d{4})(\d{2})(\d{2})',  # YYYYMMDD
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, value_str)
                if match:
                    year = match.group(1)
                    month = match.group(2).zfill(2)  # 한 자리 월을 두 자리로
                    day = match.group(3).zfill(2)  # 한 자리 일을 두 자리로
                    return f"{year}-{month}-{day}"
            
            # pandas의 to_datetime으로 파싱 시도
            try:
                parsed_date = pd.to_datetime(value_str, errors='coerce')
                if pd.notna(parsed_date):
                    return parsed_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
            
            # 파싱 실패 시 원본 값 반환 (또는 np.nan)
            return np.nan
        
        # 날짜 형식 추출 및 텍스트 변환
        result_df['eventDate'] = df[event_date_col].apply(extract_date_format)
        print(f"✅ eventDate 필드에 데이터 복사 완료: {len(result_df[result_df['eventDate'].notna()])}개 행")
        print(f"eventDate 샘플 값: {result_df['eventDate'].head(3).tolist()}")
    else:
        result_df['eventDate'] = np.nan
        print("⚠️ eventDate 필드가 비어있습니다.")
    
    # 기관코드를 institutionCode에 매핑
    if institution_code_col:
        result_df['institutionCode'] = df[institution_code_col]
        print(f"✅ institutionCode 필드에 데이터 복사 완료: {len(result_df[result_df['institutionCode'].notna()])}개 행")
        print(f"institutionCode 샘플 값: {result_df['institutionCode'].head(3).tolist()}")
    else:
        result_df['institutionCode'] = np.nan
        print("⚠️ institutionCode 필드가 비어있습니다.")
    
    # 학명을 scientificName에 매핑
    if scientific_name_col:
        result_df['scientificName'] = df[scientific_name_col]
        print(f"✅ scientificName 필드에 데이터 복사 완료: {len(result_df[result_df['scientificName'].notna()])}개 행")
        print(f"scientificName 샘플 값: {result_df['scientificName'].head(3).tolist()}")
    else:
        result_df['scientificName'] = np.nan
        print("⚠️ scientificName 필드가 비어있습니다.")
    
    # 위도를 decimalLatitude에 매핑 (숫자형으로 변환)
    if latitude_col:
        result_df['decimalLatitude'] = pd.to_numeric(df[latitude_col], errors='coerce')
        print(f"✅ decimalLatitude 필드에 데이터 복사 완료: {len(result_df[result_df['decimalLatitude'].notna()])}개 행")
        print(f"decimalLatitude 샘플 값: {result_df['decimalLatitude'].head(3).tolist()}")
    else:
        result_df['decimalLatitude'] = np.nan
        print("⚠️ decimalLatitude 필드가 비어있습니다.")
    
    # 경도를 decimalLongitude에 매핑 (숫자형으로 변환)
    if longitude_col:
        result_df['decimalLongitude'] = pd.to_numeric(df[longitude_col], errors='coerce')
        print(f"✅ decimalLongitude 필드에 데이터 복사 완료: {len(result_df[result_df['decimalLongitude'].notna()])}개 행")
        print(f"decimalLongitude 샘플 값: {result_df['decimalLongitude'].head(3).tolist()}")
    else:
        result_df['decimalLongitude'] = np.nan
        print("⚠️ decimalLongitude 필드가 비어있습니다.")
    
    # 국가영문명을 countryCode에 매핑 (국가명을 ISO 3166-1 alpha-2 코드로 변환)
    def convert_country_name_to_code(country_name):
        """국가명을 ISO 3166-1 alpha-2 국가 코드로 변환"""
        if pd.isna(country_name):
            return np.nan
        
        country_str = str(country_name).strip()
        
        # 이미 2자리 코드인 경우 그대로 반환
        if len(country_str) == 2 and country_str.isalpha():
            return country_str.upper()
        
        # 국가명 -> 국가 코드 매핑 (주요 국가)
        country_mapping = {
            'republic of korea': 'KR',
            'korea': 'KR',
            'south korea': 'KR',
            'korea, republic of': 'KR',
            'united states': 'US',
            'united states of america': 'US',
            'usa': 'US',
            'china': 'CN',
            'people\'s republic of china': 'CN',
            'japan': 'JP',
            'russia': 'RU',
            'russian federation': 'RU',
            'united kingdom': 'GB',
            'uk': 'GB',
            'germany': 'DE',
            'france': 'FR',
            'italy': 'IT',
            'spain': 'ES',
            'canada': 'CA',
            'australia': 'AU',
            'india': 'IN',
            'brazil': 'BR',
            'mexico': 'MX',
            'thailand': 'TH',
            'vietnam': 'VN',
            'philippines': 'PH',
            'indonesia': 'ID',
            'malaysia': 'MY',
            'singapore': 'SG',
            'taiwan': 'TW',
            'north korea': 'KP',
            'korea, democratic people\'s republic of': 'KP',
        }
        
        # 대소문자 무시하고 매핑 검색
        country_lower = country_str.lower()
        for country_key, country_code in country_mapping.items():
            if country_key in country_lower or country_lower in country_key:
                return country_code
        
        # 매핑에 없으면 원본 반환 (또는 np.nan)
        return country_str
    
    if country_name_col:
        result_df['countryCode'] = df[country_name_col].apply(convert_country_name_to_code)
        print(f"✅ countryCode 필드에 데이터 복사 완료: {len(result_df[result_df['countryCode'].notna()])}개 행")
        print(f"countryCode 샘플 값: {result_df['countryCode'].head(3).tolist()}")
    else:
        result_df['countryCode'] = np.nan
        print("⚠️ countryCode 필드가 비어있습니다.")
    
    # 동정년월일을 dateIdentified에 매핑 (날짜 형식만 추출하여 텍스트로 저장)
    if date_identified_col:
        # 관찰일자와 동일한 날짜 형식 추출 함수 사용
        def extract_date_format(value):
            """날짜 형식(####-##-##)만 추출하여 YYYY-MM-DD 텍스트 형식으로 반환"""
            if pd.isna(value):
                return np.nan
            
            value_str = str(value).strip()
            
            # 이미 YYYY-MM-DD 형식인 경우
            if re.match(r'^\d{4}-\d{2}-\d{2}$', value_str):
                return value_str
            
            # 날짜 형식 추출 (YYYY-MM-DD 또는 YYYY/MM/DD 등)
            # 다양한 날짜 형식 패턴 시도
            date_patterns = [
                r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',  # YYYY-MM-DD, YYYY/MM/DD
                r'(\d{4})(\d{2})(\d{2})',  # YYYYMMDD
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, value_str)
                if match:
                    year = match.group(1)
                    month = match.group(2).zfill(2)  # 한 자리 월을 두 자리로
                    day = match.group(3).zfill(2)  # 한 자리 일을 두 자리로
                    return f"{year}-{month}-{day}"
            
            # pandas의 to_datetime으로 파싱 시도
            try:
                parsed_date = pd.to_datetime(value_str, errors='coerce')
                if pd.notna(parsed_date):
                    return parsed_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
            
            # 파싱 실패 시 원본 값 반환 (또는 np.nan)
            return np.nan
        
        # 날짜 형식 추출 및 텍스트 변환
        result_df['dateIdentified'] = df[date_identified_col].apply(extract_date_format)
        print(f"✅ dateIdentified 필드에 데이터 복사 완료: {len(result_df[result_df['dateIdentified'].notna()])}개 행")
        print(f"dateIdentified 샘플 값: {result_df['dateIdentified'].head(3).tolist()}")
    else:
        result_df['dateIdentified'] = np.nan
        print("⚠️ dateIdentified 필드가 비어있습니다.")
    
    # 동정자 영문을 identifiedBy에 매핑
    if identified_by_col:
        result_df['identifiedBy'] = df[identified_by_col]
        print(f"✅ identifiedBy 필드에 데이터 복사 완료: {len(result_df[result_df['identifiedBy'].notna()])}개 행")
        print(f"identifiedBy 샘플 값: {result_df['identifiedBy'].head(3).tolist()}")
    else:
        result_df['identifiedBy'] = np.nan
        print("⚠️ identifiedBy 필드가 비어있습니다.")
    
    # 관찰위치 시도 영문을 stateProvince에 매핑
    if state_province_col:
        result_df['stateProvince'] = df[state_province_col]
        print(f"✅ stateProvince 필드에 데이터 복사 완료: {len(result_df[result_df['stateProvince'].notna()])}개 행")
        print(f"stateProvince 샘플 값: {result_df['stateProvince'].head(3).tolist()}")
    else:
        result_df['stateProvince'] = np.nan
        print("⚠️ stateProvince 필드가 비어있습니다.")
    
    # 관찰 위치 시군구 영문을 county에 매핑
    if county_col:
        result_df['county'] = df[county_col]
        print(f"✅ county 필드에 데이터 복사 완료: {len(result_df[result_df['county'].notna()])}개 행")
        print(f"county 샘플 값: {result_df['county'].head(3).tolist()}")
    else:
        result_df['county'] = np.nan
        print("⚠️ county 필드가 비어있습니다.")
    
    # 관찰위치 읍면동 영문을 locality에 매핑
    if locality_col:
        result_df['locality'] = df[locality_col]
        print(f"✅ locality 필드에 데이터 복사 완료: {len(result_df[result_df['locality'].notna()])}개 행")
        print(f"locality 샘플 값: {result_df['locality'].head(3).tolist()}")
    else:
        result_df['locality'] = np.nan
        print("⚠️ locality 필드가 비어있습니다.")
    
    # 관찰위치 상세 영문을 verbatimLocality에 매핑
    if verbatim_locality_col:
        result_df['verbatimLocality'] = df[verbatim_locality_col]
        print(f"✅ verbatimLocality 필드에 데이터 복사 완료: {len(result_df[result_df['verbatimLocality'].notna()])}개 행")
        print(f"verbatimLocality 샘플 값: {result_df['verbatimLocality'].head(3).tolist()}")
    else:
        result_df['verbatimLocality'] = np.nan
        print("⚠️ verbatimLocality 필드가 비어있습니다.")
    
    # 국명을 vernacularName에 매핑
    if vernacular_name_col:
        result_df['vernacularName'] = df[vernacular_name_col]
        print(f"✅ vernacularName 필드에 데이터 복사 완료: {len(result_df[result_df['vernacularName'].notna()])}개 행")
        print(f"vernacularName 샘플 값: {result_df['vernacularName'].head(3).tolist()}")
    else:
        result_df['vernacularName'] = np.nan
        print("⚠️ vernacularName 필드가 비어있습니다.")
    
    # 매핑 규칙에 따라 데이터 복사
    for normalized_korean, gbif_field in korean_to_gbif_mapping.items():
        # occurrenceID, eventDate, institutionCode, scientificName, decimalLatitude, decimalLongitude, countryCode, dateIdentified, identifiedBy, stateProvince, county, locality, verbatimLocality, vernacularName는 이미 처리했으므로 스킵
        if gbif_field in ['occurrenceID', 'eventDate', 'institutionCode', 'scientificName', 'decimalLatitude', 'decimalLongitude', 'countryCode', 'dateIdentified', 'identifiedBy', 'stateProvince', 'county', 'locality', 'verbatimLocality', 'vernacularName']:
            continue
            
        source_col = normalized_columns.get(normalized_korean)
        if source_col:
            result_df[gbif_field] = df[source_col]
        else:
            result_df[gbif_field] = np.nan
    
    # basisOfRecord 필드 처리
    if basis_of_record:
        # 사용자가 선택한 값으로 전체 데이터에 적용
        result_df['basisOfRecord'] = basis_of_record
    elif 'basisOfRecord' not in result_df.columns or result_df['basisOfRecord'].isna().all():
        # 매핑된 값이 없으면 기본값 설정
        result_df['basisOfRecord'] = np.nan
    
    # catalogNumber가 비어있고 occurrenceID가 있으면 occurrenceID 값을 사용
    if 'catalogNumber' in result_df.columns and 'occurrenceID' in result_df.columns:
        result_df['catalogNumber'] = result_df['catalogNumber'].where(
            result_df['catalogNumber'].notna(),
            result_df['occurrenceID']
        )
    
    # 모든 GBIF 필드가 결과에 포함되도록 보장
    for gbif_col in gbif_columns:
        if gbif_col not in result_df.columns:
            result_df[gbif_col] = np.nan
    
    # GBIF 필드 순서대로 정렬
    result_df = result_df[gbif_columns]
    
    # 위도/경도는 이미 숫자형으로 변환되었으므로 추가 변환 불필요
    
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

