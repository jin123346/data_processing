import streamlit as st
import pandas as pd
import os
import re
from pathlib import Path
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from preprocessors import convert_to_gbif, convert_to_naver, convert_to_bioone

NAVER_OPTION = "네이버백과사전으로 변환"

# 페이지 설정
st.set_page_config(
    page_title="데이터 전처리 시스템",
    page_icon="📊",
    layout="wide"
)

st.title("📊 엑셀 데이터 전처리 시스템")

# 세션 상태 초기화
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'original_data' not in st.session_state:
    st.session_state.original_data = None
if 'preprocessing_option' not in st.session_state:
    st.session_state.preprocessing_option = None

# 사이드바 - 파일 업로드
with st.sidebar:
    st.header("📁 파일 업로드")
    uploaded_file = st.file_uploader(
        "엑셀 파일을 선택하세요",
        type=['xlsx', 'xls'],
        help=".xlsx 또는 .xls 형식의 파일을 업로드하세요"
    )
    
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        st.success(f"✅ 파일 업로드 완료: {uploaded_file.name}")

# 메인 영역
if st.session_state.uploaded_file is not None:
    # 데이터 로드
    try:
        if st.session_state.original_data is None:
            with st.spinner("데이터를 불러오는 중..."):
                try:
                    # 엑셀 파일의 시트 목록 확인
                        
                    excel_file = pd.ExcelFile(st.session_state.uploaded_file)
                    sheet_names = excel_file.sheet_names
                    
                    # "정보입력" 시트 찾기
                    target_sheet = None
                    for sheet in sheet_names:
                        if "정보입력" in sheet:
                            target_sheet = sheet
                            break
                    
                    # "정보입력" 시트가 없으면 첫 번째 시트 사용
                    if target_sheet is None:
                        target_sheet = sheet_names[0] if sheet_names else None
                        if target_sheet:
                            st.warning(f"⚠️ '정보입력' 시트를 찾을 수 없어 '{target_sheet}' 시트를 사용합니다.")
                        else:
                            st.error("❌ 엑셀 파일에 시트가 없습니다.")
                            st.stop()
                    else:
                        st.success(f"✅ '{target_sheet}' 시트에서 데이터를 읽어옵니다.")
                    
                    # 파일 포인터를 다시 처음으로 이동
                    st.session_state.uploaded_file.seek(0)
                    
                    # 먼저 첫 네 행을 읽어서 헤더 구조 확인
                    temp_df = pd.read_excel(excel_file, sheet_name=target_sheet, nrows=4, header=None)
                    
                    # 첫 번째 행과 두 번째 행이 헤더인지 확인
                    has_two_row_header = False
                    if len(temp_df) >= 3:
                        # 더 정확한 헤더 감지 로직
                        # 1. 첫 번째 행이 한글 컬럼명인지 확인
                        # 2. 두 번째 행이 설명 형식(괄호 안에 설명, "자동생성", "입력" 등)인지 확인
                        # 3. 세 번째 행이 실제 데이터인지 확인
                        first_row_is_header = False
                        second_row_is_header = False
                        third_row_is_data = False
                        
                        for col_idx in range(min(len(temp_df.columns), 10)):  # 처음 10개 컬럼만 확인
                            first_val = str(temp_df.iloc[0, col_idx]) if pd.notna(temp_df.iloc[0, col_idx]) else ""
                            second_val = str(temp_df.iloc[1, col_idx]) if pd.notna(temp_df.iloc[1, col_idx]) else ""
                            third_val = str(temp_df.iloc[2, col_idx]) if pd.notna(temp_df.iloc[2, col_idx]) else ""
                            
                            # 첫 번째 행이 한글 컬럼명인지 확인 (한글이 포함되어 있고 짧은 경우)
                            if first_val and any('\uac00' <= char <= '\ud7a3' for char in first_val):
                                if len(first_val.strip()) < 20:  # 한글 컬럼명은 보통 짧음
                                    first_row_is_header = True
                            
                            # 두 번째 행이 헤더 설명인지 확인 (괄호 안에 설명이 있거나 특정 키워드 포함)
                            # 단, 학명처럼 괄호 안에 저자명이 있는 경우는 제외
                            if second_val:
                                # 설명 형식: 괄호 안에 한글이 있거나, 특정 키워드가 있으면 헤더
                                if ('(' in second_val and any('\uac00' <= char <= '\ud7a3' for char in second_val)) or \
                                   '자동생성' in second_val or '입력' in second_val or '선택' in second_val:
                                    # 괄호 안에 한글이 있으면 설명으로 간주
                                    second_row_is_header = True
                            
                            # 세 번째 행이 실제 데이터인지 확인
                            if third_val:
                                # 학명 형식(영문 + 괄호)이거나, 숫자, 날짜, 긴 텍스트면 데이터
                                if (re.match(r'^[A-Za-z\s]+\([^)]+\)', third_val.strip()) or  # 학명 형식
                                    third_val.replace('.', '').replace('-', '').isdigit() or  # 숫자
                                    len(third_val.strip()) > 10 or  # 긴 텍스트
                                    re.match(r'\d{4}[-/]\d', third_val)):  # 날짜
                                    third_row_is_data = True
                        
                        # 첫 번째 행이 헤더이고, 두 번째 행도 헤더 설명이고, 세 번째 행이 데이터면 2행 헤더로 판단
                        if first_row_is_header and second_row_is_header and third_row_is_data:
                            has_two_row_header = True
                    
                    if has_two_row_header:
                        # 첫 번째 행과 두 번째 행을 합쳐서 컬럼명 생성
                        combined_headers = []
                        for col_idx in range(len(temp_df.columns)):
                            first_row_val = str(temp_df.iloc[0, col_idx]) if pd.notna(temp_df.iloc[0, col_idx]) else ""
                            second_row_val = str(temp_df.iloc[1, col_idx]) if pd.notna(temp_df.iloc[1, col_idx]) else ""
                            
                            # 두 값을 합치되, 공백으로 구분
                            if first_row_val and second_row_val:
                                combined_header = f"{first_row_val} {second_row_val}".strip()
                            elif first_row_val:
                                combined_header = first_row_val
                            elif second_row_val:
                                combined_header = second_row_val
                            else:
                                combined_header = f"Unnamed_{col_idx}"
                            
                            combined_headers.append(combined_header)
                        
                        # 실제 데이터 읽기 (3번째 행부터, 헤더는 None으로 설정)
                        df = pd.read_excel(excel_file, sheet_name=target_sheet, header=None, skiprows=2)
                        # 컬럼 수가 맞지 않으면 조정
                        if len(df.columns) > len(combined_headers):
                            # 부족한 헤더 추가
                            for i in range(len(combined_headers), len(df.columns)):
                                combined_headers.append(f"Unnamed_{i}")
                        elif len(df.columns) < len(combined_headers):
                            # 헤더가 더 많으면 자름
                            combined_headers = combined_headers[:len(df.columns)]
                        df.columns = combined_headers[:len(df.columns)]
                    else:
                        # 헤더가 한 행만 있는 경우 (일반적인 경우)
                        df = pd.read_excel(excel_file, sheet_name=target_sheet, header=0)
                    
                    # 빈 행 제거
                    df = df.dropna(how='all')
                    
                    # 데이터가 비어있는지 확인
                    if df.empty:
                        st.error("❌ 읽어온 데이터가 비어있습니다. 엑셀 파일의 구조를 확인해주세요.")
                        st.info("💡 디버깅 정보: 시트명 목록 = " + ", ".join(sheet_names))
                    else:
                        st.session_state.original_data = df
                        
                except Exception as e:
                    st.error(f"❌ 데이터를 읽는 중 오류가 발생했습니다: {str(e)}")
                    st.exception(e)
                    st.info("💡 엑셀 파일 형식이 올바른지 확인해주세요.")
                    st.stop()
        
        df = st.session_state.original_data
        
        # 데이터 미리보기
        st.subheader("📋 업로드된 데이터 미리보기")
        st.dataframe(df.head(10), use_container_width=True)
        st.info(f"총 {len(df)}개의 행, {len(df.columns)}개의 열이 있습니다.")
        
        # 전처리 옵션 선택
        st.divider()
        st.subheader("⚙️ 데이터 전처리 옵션 선택")
        
        preprocessing_option = st.radio(
            "변환할 형식을 선택하세요:",
            ["GBIF로 변환", NAVER_OPTION, "바이오원으로 변환"],
            horizontal=True
        )
        
        # GBIF 변환 선택 시 표본/관찰 선택 옵션 표시
        basis_of_record = None
        if preprocessing_option == "GBIF로 변환":
            st.divider()
            st.subheader("📋 GBIF 변환 설정")
            basis_of_record = st.radio(
                "표본/관찰 선택:",
                ["관찰", "표본"],
                horizontal=True,
                help="관찰을 선택하면 HumanObservation, 표본을 선택하면 PreservedSpecimen이 전체 데이터에 적용됩니다."
            )
        
        # 전처리 실행 버튼
        if st.button("🔄 전처리 실행", type="primary", use_container_width=True):
            with st.spinner(f"{preprocessing_option} 중..."):
                try:
                    if preprocessing_option == "GBIF로 변환":
                        # basisOfRecord 값 설정
                        if basis_of_record:
                            basis_value = "HumanObservation" if basis_of_record == "관찰" else "PreservedSpecimen"
                            processed_df = convert_to_gbif(df.copy(), basis_of_record=basis_value)
                        else:
                            processed_df = convert_to_gbif(df.copy())
                    elif preprocessing_option == NAVER_OPTION:
                        processed_df = convert_to_naver(df.copy())
                    elif preprocessing_option == "바이오원으로 변환":
                        processed_df = convert_to_bioone(df.copy())
                    
                    st.session_state.processed_data = processed_df
                    st.session_state.preprocessing_option = preprocessing_option
                    st.success(f"✅ {preprocessing_option} 완료!")
                except Exception as e:
                    st.error(f"❌ 전처리 중 오류가 발생했습니다: {str(e)}")
        
        # 전처리된 데이터 표시
        if st.session_state.processed_data is not None:
            st.divider()
            st.subheader("✨ 전처리된 데이터 미리보기")
            st.dataframe(st.session_state.processed_data.head(10), use_container_width=True)
            
            # 저장 옵션
            st.divider()
            st.subheader("💾 파일 저장")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                save_path = st.text_input(
                    "저장할 경로를 입력하세요:",
                    value=str(Path.home() / "Downloads"),
                    help="파일을 저장할 폴더 경로를 입력하세요"
                )
            
            with col2:
                file_name = st.text_input(
                    "파일 이름:",
                    value="processed_data.xlsx",
                    help="저장할 파일 이름을 입력하세요"
                )
            
            # 저장 버튼
            if st.button("💾 엑셀 파일로 저장", type="primary", use_container_width=True):
                try:
                    full_path = Path(save_path) / file_name
                    
                    # 디렉토리가 없으면 생성
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 네이버 백과사전 변환의 경우 컬럼명을 올바르게 설정
                    current_option = st.session_state.preprocessing_option or preprocessing_option
                    if current_option == NAVER_OPTION and {'개체명(국2)_1', '개체명(국2)_2'}.issubset(set(st.session_state.processed_data.columns)):
                        # openpyxl을 사용하여 같은 이름의 컬럼을 처리
                        wb = Workbook()
                        ws = wb.active
                        
                        # 컬럼명 설정 (개체명(국2)를 두 번, 빈 컬럼 처리)
                        column_names = [
                            '신고일자',
                            '개체명(국2)',
                            '개체명(국2)',  # 같은 이름
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
                        
                        # 헤더 작성
                        ws.append(column_names)
                        
                        # 데이터 작성
                        for r in dataframe_to_rows(st.session_state.processed_data, index=False, header=False):
                            ws.append(r)
                        
                        wb.save(full_path)
                    else:
                        # 다른 변환 형식은 일반적인 방법 사용
                        st.session_state.processed_data.to_excel(full_path, index=False, engine='openpyxl')
                    
                    st.success(f"✅ 파일이 성공적으로 저장되었습니다!\n경로: {full_path}")
                    
                    # 다운로드 버튼 제공
                    with open(full_path, "rb") as file:
                        st.download_button(
                            label="📥 파일 다운로드",
                            data=file.read(),
                            file_name=file_name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"❌ 파일 저장 중 오류가 발생했습니다: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ 파일을 읽는 중 오류가 발생했습니다: {str(e)}")
        st.info("파일 형식이 올바른지 확인해주세요.")

else:
    # 초기 화면
    st.info("👈 왼쪽 사이드바에서 엑셀 파일을 업로드해주세요.")
    
    st.markdown("""
    ### 사용 방법:
    1. **파일 업로드**: 왼쪽 사이드바에서 엑셀 파일(.xlsx, .xls)을 선택합니다.
    2. **데이터 확인**: 업로드된 데이터의 미리보기를 확인합니다.
    3. **전처리 선택**: 원하는 변환 형식을 선택합니다.
       - GBIF로 변환
       - 네이버백과사전으로 변환
       - 바이오원으로 변환
    4. **전처리 실행**: 선택한 옵션으로 데이터를 변환합니다.
    5. **파일 저장**: 변환된 데이터를 엑셀 파일로 저장합니다.
    """)

