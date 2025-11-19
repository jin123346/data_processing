import streamlit as st
import pandas as pd
import os
from pathlib import Path
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from preprocessors import convert_to_gbif, convert_to_naver, convert_to_bioone

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
                df = pd.read_excel(st.session_state.uploaded_file)
                st.session_state.original_data = df
        
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
            ["GBIF로 변환", "네이버백과사전으로 변환", "바이오원으로 변환"],
            horizontal=True
        )
        
        # 전처리 실행 버튼
        if st.button("🔄 전처리 실행", type="primary", use_container_width=True):
            with st.spinner(f"{preprocessing_option} 중..."):
                try:
                    if preprocessing_option == "GBIF로 변환":
                        processed_df = convert_to_gbif(df.copy())
                    elif preprocessing_option == "네이버백과사전으로 변환":
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
                    if current_option == "네이버백과사전으로 변환":
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

