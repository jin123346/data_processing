import pandas as pd
import numpy as np

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
    데이터를 네이버백과사전 형식으로 변환합니다.
    입력 형식: Id, 분류 세기 라틴명, 분류 세기 명, 분류군 scnm, comm, 업데이트 유무, 상태, 
              적 특징, 서식지, 행동 습성, 국내 분포, 국외 분포, 원반적, 특징, 기, 주요 형질, 
              천연기념물 멸종위기 보호식물
    출력 형식: 신고일자, 개체명(국2), 개체명(국2), 개체명, 구분, 지, 회사, (빈 컬럼),
              크기, 색과 무늬, 주요 특징, 서식지, 먹이 습성, 행동 습성, 국내 분포, 국외 분포, 전체 정보
    """
    # 네이버백과사전 출력 형식 필드
    naver_columns = [
        '신고일자',
        '개체명(국2)',  # 첫 번째
        '개체명(국2)',  # 두 번째 (중복 이름)
        '개체명',
        '구분',
        '지',
        '회사',
        '',  # 빈 컬럼
        '크기',
        '색과 무늬',
        '주요 특징',
        '서식지',
        '먹이 습성',
        '행동 습성',
        '국내 분포',
        '국외 분포',
        '전체 정보'
    ]
    
    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame()
    
    # 입력 컬럼명 정규화 (공백 제거, 대소문자 통일)
    df_columns_normalized = {col.strip(): col for col in df.columns}
    
    # 컬럼 매핑 정의
    def find_column(keywords):
        """키워드 리스트로 컬럼 찾기"""
        for keyword in keywords:
            for norm_col, orig_col in df_columns_normalized.items():
                if keyword in norm_col:
                    return orig_col
        return None
    
    # 매핑 수행
    # 신고일자: 업데이트 유무나 상태에서 날짜 정보가 있다면 사용, 없으면 빈 값
    result_df['신고일자'] = np.nan
    
    # 개체명(국2) 첫 번째: comm 컬럼
    comm_col = find_column(['comm', 'Comm'])
    if comm_col:
        result_df['개체명(국2)_1'] = df[comm_col]
    else:
        result_df['개체명(국2)_1'] = np.nan
    
    # 개체명(국2) 두 번째: 분류 세기 명
    분류세기명_col = find_column(['분류 세기 명', '분류세기명'])
    if 분류세기명_col:
        result_df['개체명(국2)_2'] = df[분류세기명_col]
    else:
        result_df['개체명(국2)_2'] = np.nan
    
    # 개체명: comm 또는 분류 세기 명
    if comm_col:
        result_df['개체명'] = df[comm_col]
    elif 분류세기명_col:
        result_df['개체명'] = df[분류세기명_col]
    else:
        result_df['개체명'] = np.nan
    
    # 구분: 상태 컬럼
    상태_col = find_column(['상태'])
    if 상태_col:
        result_df['구분'] = df[상태_col]
    else:
        result_df['구분'] = np.nan
    
    # 지: 원반적 컬럼
    원반적_col = find_column(['원반적'])
    if 원반적_col:
        result_df['지'] = df[원반적_col]
    else:
        result_df['지'] = np.nan
    
    # 회사: 없으면 빈 값
    result_df['회사'] = np.nan
    
    # 빈 컬럼
    result_df[''] = np.nan
    
    # 크기: 주요 형질 또는 특징
    주요형질_col = find_column(['주요 형질', '주요형질'])
    특징_col = find_column(['특징'])
    if 주요형질_col:
        result_df['크기'] = df[주요형질_col]
    elif 특징_col:
        result_df['크기'] = df[특징_col]
    else:
        result_df['크기'] = np.nan
    
    # 색과 무늬: 특징 컬럼
    if 특징_col:
        result_df['색과 무늬'] = df[특징_col]
    else:
        result_df['색과 무늬'] = np.nan
    
    # 주요 특징: 특징 컬럼
    if 특징_col:
        result_df['주요 특징'] = df[특징_col]
    else:
        result_df['주요 특징'] = np.nan
    
    # 서식지: 서식지 컬럼
    서식지_col = find_column(['서식지'])
    if 서식지_col:
        result_df['서식지'] = df[서식지_col]
    else:
        result_df['서식지'] = np.nan
    
    # 먹이 습성: 적 특징 또는 주요 형질
    적특징_col = find_column(['적 특징', '적특징', '생물적 특징'])
    if 적특징_col:
        result_df['먹이 습성'] = df[적특징_col]
    elif 주요형질_col:
        result_df['먹이 습성'] = df[주요형질_col]
    else:
        result_df['먹이 습성'] = np.nan
    
    # 행동 습성: 행동 습성 컬럼
    행동습성_col = find_column(['행동 습성', '행동습성'])
    if 행동습성_col:
        result_df['행동 습성'] = df[행동습성_col]
    else:
        result_df['행동 습성'] = np.nan
    
    # 국내 분포: 국내 분포 컬럼
    국내분포_col = find_column(['국내 분포', '국내분포'])
    if 국내분포_col:
        result_df['국내 분포'] = df[국내분포_col]
    else:
        result_df['국내 분포'] = np.nan
    
    # 국외 분포: 국외 분포 컬럼
    국외분포_col = find_column(['국외 분포', '국외분포'])
    if 국외분포_col:
        result_df['국외 분포'] = df[국외분포_col]
    else:
        result_df['국외 분포'] = np.nan
    
    # 전체 정보: 모든 정보를 합쳐서 생성 (선택적)
    # 주요 정보들을 조합하여 전체 정보 생성
    전체정보_list = []
    for idx in df.index:
        info_parts = []
        if comm_col and pd.notna(df.loc[idx, comm_col]):
            info_parts.append(str(df.loc[idx, comm_col]))
        if 분류세기명_col and pd.notna(df.loc[idx, 분류세기명_col]):
            info_parts.append(str(df.loc[idx, 분류세기명_col]))
        if 특징_col and pd.notna(df.loc[idx, 특징_col]):
            info_parts.append(str(df.loc[idx, 특징_col]))
        
        if info_parts:
            전체정보_list.append(' | '.join(info_parts))
        else:
            전체정보_list.append('')
    
    result_df['전체 정보'] = 전체정보_list
    
    # 컬럼 순서 재정렬
    # pandas는 같은 이름의 컬럼을 허용하지 않으므로, 
    # 엑셀 저장 시에만 같은 이름으로 처리하기 위해 여기서는 구분된 이름 사용
    final_columns = [
        '신고일자',
        '개체명(국2)_1',
        '개체명(국2)_2',
        '개체명',
        '구분',
        '지',
        '회사',
        '빈컬럼',
        '크기',
        '색과 무늬',
        '주요 특징',
        '서식지',
        '먹이 습성',
        '행동 습성',
        '국내 분포',
        '국외 분포',
        '전체 정보'
    ]
    
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

