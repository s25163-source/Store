import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 제목 표시
# ==========================================
st.set_page_config(
    page_title="편의점 & 카페 지도 검색", page_icon="🏪", layout="wide"
)

st.title("🏪 편의점 & 카페 위치 안내 지도")
st.caption(
    "시/도별 선택 및 특정 매장 기준 반경 내 매장 검색 기능을 제공합니다."
)


# ==========================================
# 2. 하버사인(Haversine) 거리 계산 함수 정의
# ==========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """두 위도/경도 좌표 간의 대권 거리(km)를 하버사인 공식으로 계산합니다."""
    R = 6371.0  # 지구 반지름 (단위: km)

    # 도(degree)를 라디안(radian)으로 변환
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distance = R * c
    return distance


# ==========================================
# 3. 데이터 불러오기 및 전처리 (캐싱 적용)
# ==========================================
@st.cache_data
def load_data():
    # 파일 존재 여부 확인 후 로드 (store.csv -> store_filtered.csv 순서로 시도)
    file_path = "store.csv"
    if not os.path.exists(file_path):
        if os.path.exists("store_filtered.csv"):
            file_path = "store_filtered.csv"
        else:
            st.error(
                "데이터 파일(store.csv 또는 store_filtered.csv)을 찾을 수 없습니다."
            )
            return pd.DataFrame()

    df = pd.read_csv(file_path)

    # 필수 열 존재 여부 확인
    required_cols = ["상호명", "위도", "경도", "상권업종소분류명", "시도명"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"데이터셋에 필수 열 '{col}'이(가) 없습니다.")
            return pd.DataFrame()

    # 업종 필터링 ("편의점", "카페"만 추출)
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    # 위도, 경도 숫자형 변환 및 결측치 제거
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    return df


df_raw = load_data()

# 데이터가 비어있는 경우 앱 진행 중단
if df_raw.empty:
    st.warning("표시할 데이터가 없습니다. CSV 파일을 확인해주세요.")
    st.stop()


# ==========================================
# 4. 사이드바 - 지역 및 옵션 선택 UI
# ==========================================
st.sidebar.header("🔍 검색 및 필터 옵션")

# 1) 시/도 선택
sido_list = sorted(df_raw["시도명"].dropna().unique())
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

# 선택한 시/도의 데이터만 1차 필터링
df_filtered = df_raw[df_raw["시도명"] == selected_sido].copy()

st.sidebar.markdown("---")

# 2) 반경 검색 옵션
use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")

selected_center_store = None
radius_km = 1.0

if use_radius_search:
    st.sidebar.subheader("📍 반경 검색 설정")

    # 선택한 시/도 내 매장 목록에서 기준 매장 선택
    store_options = (
        df_filtered["상호명"] + " (" + df_filtered["상권업종소분류명"] + ")"
    )
    selected_store_label = st.sidebar.selectbox(
        "기준 매장 선택",
        options=store_options,
        index=0 if len(store_options) > 0 else None,
    )

    # 검색 반경 슬라이더 (0.5km ~ 10.0km)
    radius_km = st.sidebar.slider(
        "검색 반경 (km)",
        min_value=0.5,
        max_value=10.0,
        value=1.0,
        step=0.5,
    )

    if selected_store_label:
        # 선택한 매장의 정보 가져오기
        selected_idx = store_options[
            store_options == selected_store_label
        ].index[0]
        selected_center_store = df_filtered.loc[selected_idx]

        # 거리 계산
        distances = haversine_distance(
            selected_center_store["위도"],
            selected_center_store["경도"],
            df_filtered["위도"],
            df_filtered["경도"],
        )

        # 설정한 반경 내 매장만 필터링
        df_filtered = df_filtered[distances <= radius_km]


# ==========================================
# 5. 메인 화면 - 지표 카드(st.metric) 표시
# ==========================================
if use_radius_search and selected_center_store is not None:
    st.subheader(
        f"📍 [{selected_center_store['상호명']}] 기준 반경 {radius_km}km 이내"
    )

# 각 업종별 개수 집계
total_count = len(df_filtered)
convenience_count = len(
    df_filtered[df_filtered["상권업종소분류명"] == "편의점"]
)
cafe_count = len(df_filtered[df_filtered["상권업종소분류명"] == "카페"])

# 3개의 컬럼으로 지표 표시
col1, col2, col3 = st.columns(3)
col1.metric("전체 매장 수", f"{total_count:,} 개")
col2.metric("편의점 수", f"{convenience_count:,} 개")
col3.metric("카페 수", f"{cafe_count:,} 개")

st.markdown("---")


# ==========================================
# 6. 메인 화면 - Plotly 지도 그리기
# ==========================================
if df_filtered.empty:
    st.info("조건에 일치하는 매장이 없습니다. 검색 조건이나 반경을 변경해보세요.")
else:
    # 색상 지정: 편의점(파란색), 카페(주황색)
    color_map = {"편의점": "#1f77b4", "카페": "#ff7f0e"}

    # 지도의 중심점 및 확대 레벨 설정
    if use_radius_search and selected_center_store is not None:
        center_lat = selected_center_store["위도"]
        center_lon = selected_center_store["경도"]
        zoom_level = 13  # 반경 검색 시 중심 매장 기준으로 확대
    else:
        center_lat = df_filtered["위도"].mean()
        center_lon = df_filtered["경도"].mean()
        zoom_level = 10

    # Plotly 버전 호환 처리 (px.scatter_map 또는 px.scatter_mapbox 사용)
    map_kwargs = dict(
        data_frame=df_filtered,
        lat="위도",
        lon="경도",
        color="상권업종소분류명",
        color_discrete_map=color_map,
        hover_name="상호명",
        hover_data={"상권업종소분류명": True, "위도": False, "경도": False},
        zoom=zoom_level,
        center={"lat": center_lat, "lon": center_lon},
        height=600,
    )

    if hasattr(px, "scatter_map"):
        # Plotly 최신 버전
        fig = px.scatter_map(map_style="open-street-map", **map_kwargs)
    else:
        # Plotly 구버전 호환
        fig = px.scatter_mapbox(mapbox_style="open-street-map", **map_kwargs)

    # 레이아웃 범례 및 여백 조정
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text="업종 구분",
    )

    # Streamlit 화면에 지도 출력
    st.plotly_chart(fig, use_container_width=True)
