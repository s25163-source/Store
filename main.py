import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="편의점 & 카페 지도 검색", page_icon="🏪", layout="wide"
)

# ==========================================
# 2. 다크 모드 / 라이트 모드 (온오프 토글) 처리
# ==========================================
# 세션 상태에 테마 모드 저장 (기본값: 라이트 모드)
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

# 사이드바 상단에 테마 모드 토글 버튼 생성
st.sidebar.header("🎨 테마 설정")
is_dark = st.sidebar.toggle(
    "🌙 검정색 배경 (다크 모드)",
    value=(st.session_state.theme_mode == "dark"),
)

# 토글 상태 반영
if is_dark:
    st.session_state.theme_mode = "dark"
else:
    st.session_state.theme_mode = "light"

# 테마별 CSS 스타일 및 Plotly 템플릿 적용
if st.session_state.theme_mode == "dark":
    # 딥 블랙 배경(#000000) 및 다크 테마 커스텀 CSS
    st.markdown(
        """
        <style>
        /* 1. 전체 앱 화면 및 사이드바 배경을 완전한 검은색으로 설정 */
        .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] {
            background-color: #000000 !important;
            color: #ffffff !important;
        }

        /* 2. 일반 텍스트, 라벨, 헤더를 선명한 흰색으로 설정 */
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: #ffffff !important;
        }

        /* 3. 지표 카드(st.metric) 어두운 카드 배경 스타일 적용 */
        [data-testid="stMetric"] {
            background-color: #121212 !important;
            border: 1px solid #2d2d2d !important;
            border-radius: 10px;
            padding: 12px;
        }
        [data-testid="stMetricValue"] {
            color: #00e676 !important; /* 숫자 강조색 (형광 녹색) */
        }
        [data-testid="stMetricLabel"] {
            color: #b0bec5 !important;
        }

        /* 4. 입력 폼 컴포넌트(셀렉트박스, 슬라이더 등) 다크 스타일 적용 */
        div[data-baseweb="select"] > div {
            background-color: #1e1e1e !important;
            color: #ffffff !important;
            border-color: #333333 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    plotly_template = "plotly_dark"
else:
    # 화이트 라이트 모드 커스텀 CSS
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            background-color: #f8f9fa !important;
            border: 1px solid #e9ecef !important;
            border-radius: 10px;
            padding: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    plotly_template = "plotly_white"

# ==========================================
# 3. 타이틀 표시
# ==========================================
st.title("🏪 편의점 & 카페 위치 안내 지도")
st.caption(
    "시/도 및 동별 분류 선택, 특정 매장 기준 반경 내 매장 검색 기능을 제공합니다."
)


# ==========================================
# 4. 하버사인(Haversine) 거리 계산 함수 정의
# ==========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """두 위도/경도 좌표 간의 대권 거리(km)를 하버사인 공식으로 계산합니다."""
    R = 6371.0  # 지구 반지름 (단위: km)

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
# 5. 데이터 불러오기 및 전처리 (캐싱 적용)
# ==========================================
@st.cache_data
def load_data():
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

    required_cols = ["상호명", "위도", "경도", "상권업종소분류명", "시도명"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"데이터셋에 필수 열 '{col}'이(가) 없습니다.")
            return pd.DataFrame()

    # 동명 컬럼 자동 지정
    dong_col = None
    for candidate in ["행정동명", "법정동명", "동명"]:
        if candidate in df.columns:
            dong_col = candidate
            break

    if dong_col:
        df["동명"] = df[dong_col].fillna("기타/미분류")
    else:
        df["동명"] = "전체"

    # 업종 필터링 ("편의점", "카페"만 추출)
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    # 위도, 경도 숫자형 변환 및 결측치 제거
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    return df


df_raw = load_data()

if df_raw.empty:
    st.warning("표시할 데이터가 없습니다. CSV 파일을 확인해주세요.")
    st.stop()


# ==========================================
# 6. 사이드바 - 지역(시/도, 동) 및 필터 옵션 UI
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("🔍 검색 및 필터 옵션")

# 1) 시/도 선택
sido_list = sorted(df_raw["시도명"].dropna().unique())
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

# 선택한 시/도의 데이터만 1차 필터링
df_sido = df_raw[df_raw["시도명"] == selected_sido].copy()

# 2) 동 선택
dong_list = ["전체"] + sorted(df_sido["동명"].dropna().unique().tolist())
selected_dong = st.sidebar.selectbox("동 선택", dong_list)

# 동 필터링 적용
if selected_dong != "전체":
    df_filtered = df_sido[df_sido["동명"] == selected_dong].copy()
else:
    df_filtered = df_sido.copy()

st.sidebar.markdown("---")

# 3) 반경 검색 옵션
use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")

selected_center_store = None
radius_km = 1.0

if use_radius_search:
    st.sidebar.subheader("📍 반경 검색 설정")

    if df_filtered.empty:
        st.sidebar.warning("선택한 지역에 매장이 없어 반경 검색을 할 수 없습니다.")
    else:
        store_options = (
            df_filtered["상호명"]
            + " ("
            + df_filtered["상권업종소분류명"]
            + " - "
            + df_filtered["동명"]
            + ")"
        )
        selected_store_label = st.sidebar.selectbox(
            "기준 매장 선택",
            options=store_options,
            index=0 if len(store_options) > 0 else None,
        )

        radius_km = st.sidebar.slider(
            "검색 반경 (km)",
            min_value=0.5,
            max_value=10.0,
            value=1.0,
            step=0.5,
        )

        if selected_store_label:
            selected_idx = store_options[
                store_options == selected_store_label
            ].index[0]
            selected_center_store = df_filtered.loc[selected_idx]

            distances = haversine_distance(
                selected_center_store["위도"],
                selected_center_store["경도"],
                df_filtered["위도"],
                df_filtered["경도"],
            )

            df_filtered = df_filtered[distances <= radius_km]


# ==========================================
# 7. 메인 화면 - 지표 카드(st.metric) 표시
# ==========================================
if use_radius_search and selected_center_store is not None:
    st.subheader(
        f"📍 [{selected_center_store['상호명']}] 기준 반경 {radius_km}km 이내"
    )
else:
    dong_text = f" {selected_dong}" if selected_dong != "전체" else ""
    st.subheader(f"📍 {selected_sido}{dong_text} 매장 현황")

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
# 8. 메인 화면 - Plotly 지도 그리기
# ==========================================
if df_filtered.empty:
    st.info("조건에 일치하는 매장이 없습니다. 검색 조건이나 반경을 변경해보세요.")
else:
    # 색상 지정: 편의점(파란색 계열), 카페(주황색 계열)
    if st.session_state.theme_mode == "dark":
        # 다크 모드용 가시성 높은 밝은 네온 파란색 / 네온 주황색 적용
        color_map = {"편의점": "#00d2ff", "카페": "#ff9f43"}
    else:
        color_map = {"편의점": "#1f77b4", "카페": "#ff7f0e"}

    # 중심점 및 확대 레벨 설정
    if use_radius_search and selected_center_store is not None:
        center_lat = selected_center_store["위도"]
        center_lon = selected_center_store["경도"]
        zoom_level = 13
    else:
        center_lat = df_filtered["위도"].mean()
        center_lon = df_filtered["경도"].mean()
        zoom_level = 12 if selected_dong != "전체" else 10

    # Plotly 공통 파라미터
    map_kwargs = dict(
        data_frame=df_filtered,
        lat="위도",
        lon="경도",
        color="상권업종소분류명",
        color_discrete_map=color_map,
        hover_name="상호명",
        hover_data={
            "상권업종소분류명": True,
            "동명": True,
            "위도": False,
            "경도": False,
        },
        zoom=zoom_level,
        center={"lat": center_lat, "lon": center_lon},
        height=600,
    )

    # Plotly 버전 호환 처리 (px.scatter_map 또는 px.scatter_mapbox)
    if hasattr(px, "scatter_map"):
        fig = px.scatter_map(map_style="open-street-map", **map_kwargs)
    else:
        fig = px.scatter_mapbox(mapbox_style="open-street-map", **map_kwargs)

    # 테마 적용 및 레이아웃 설정
    fig.update_layout(
        template=plotly_template,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text="업종 구분",
    )

    # Streamlit 화면에 지도 출력
    st.plotly_chart(fig, use_container_width=True)
