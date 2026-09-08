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
# 2. 다크 모드 / 라이트 모드 (대형 토글 버튼) 처리
# ==========================================
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

# 토글 버튼 및 사이드바 스타일링
st.markdown(
    """
    <style>
    div[data-testid="stCheckbox"] {
        padding: 8px 12px !important;
        border-radius: 12px !important;
    }
    div[data-testid="stCheckbox"] label p {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        line-height: 1.5 !important;
    }
    div[data-testid="stCheckbox"] label [role="switch"] {
        transform: scale(1.35) !important;
        margin-right: 12px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("### 🎨 화면 테마 설정")

with st.sidebar.container(border=True):
    is_dark = st.toggle(
        "🌙 검정 배경 다크모드",
        value=(st.session_state.theme_mode == "dark"),
        help="클릭하여 다크 모드 / 화이트 모드를 전환합니다.",
    )

if is_dark:
    st.session_state.theme_mode = "dark"
else:
    st.session_state.theme_mode = "light"

# 테마에 따른 CSS 스타일 적용
if st.session_state.theme_mode == "dark":
    st.markdown(
        """
        <style>
        .stApp, [data-testid="stSidebar"] {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, div {
            color: #ffffff !important;
        }
        [data-testid="stMetric"] {
            background-color: #111111 !important;
            border: 1px solid #333333 !important;
            border-radius: 8px;
            padding: 10px;
        }
        [data-testid="stMetricValue"] {
            color: #00e676 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    plotly_template = "plotly_dark"
else:
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            background-color: #f8f9fa !important;
            border: 1px solid #e9ecef !important;
            border-radius: 8px;
            padding: 10px;
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
# 4. 하버사인(Haversine) 거리 계산 함수
# ==========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """두 위도/경도 좌표 간의 대권 거리(km)를 계산합니다."""
    R = 6371.0

    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


# ==========================================
# 5. 데이터 불러오기 및 전처리
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

    dong_col = None
    for candidate in ["행정동명", "법정동명", "동명"]:
        if candidate in df.columns:
            dong_col = candidate
            break

    if dong_col:
        df["동명"] = df[dong_col].fillna("기타/미분류")
    else:
        df["동명"] = "전체"

    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    # 범주 아이콘 명칭 추가 (지도 표기용)
    df["업종_구분"] = df["상권업종소분류명"].apply(
        lambda x: "🏪 편의점" if x == "편의점" else "☕ 카페"
    )

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

df_sido = df_raw[df_raw["시도명"] == selected_sido].copy()

# 2) 동 선택
dong_list = ["전체"] + sorted(df_sido["동명"].dropna().unique().tolist())
selected_dong = st.sidebar.selectbox("동 선택", dong_list)

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
            + df_filtered["업종_구분"]
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

total_count = len(df_filtered)
convenience_count = len(
    df_filtered[df_filtered["상권업종소분류명"] == "편의점"]
)
cafe_count = len(df_filtered[df_filtered["상권업종소분류명"] == "카페"])

col1, col2, col3 = st.columns(3)
col1.metric("전체 매장 수", f"{total_count:,} 개")
col2.metric("편의점 🏪", f"{convenience_count:,} 개")
col3.metric("카페 ☕", f"{cafe_count:,} 개")

st.markdown("---")


# ==========================================
# 8. 메인 화면 - Plotly 지도 표시
# ==========================================
if df_filtered.empty:
    st.info("조건에 일치하는 매장이 없습니다. 검색 조건이나 반경을 변경해보세요.")
else:
    # 테마별 선명한 색상 지정
    if st.session_state.theme_mode == "dark":
        color_map = {"🏪 편의점": "#00d2ff", "☕ 카페": "#ff9f43"}
    else:
        color_map = {"🏪 편의점": "#1f77b4", "☕ 카페": "#e67e22"}

    # 중심점 및 zoom 설정
    if use_radius_search and selected_center_store is not None:
        center_lat = selected_center_store["위도"]
        center_lon = selected_center_store["경도"]
        zoom_level = 13
    else:
        center_lat = df_filtered["위도"].mean()
        center_lon = df_filtered["경도"].mean()
        zoom_level = 12 if selected_dong != "전체" else 10

    # Map 공통 파라미터
    map_kwargs = dict(
        data_frame=df_filtered,
        lat="위도",
        lon="경도",
        color="업종_구분",
        color_discrete_map=color_map,
        hover_name="상호명",
        hover_data={
            "업종_구분": True,
            "동명": True,
            "상권업종소분류명": False,
            "위도": False,
            "경도": False,
        },
        zoom=zoom_level,
        center={"lat": center_lat, "lon": center_lon},
        height=620,
    )

    # Plotly scatter_map / scatter_mapbox 분기
    if hasattr(px, "scatter_map"):
        fig = px.scatter_map(map_style="open-street-map", **map_kwargs)
    else:
        fig = px.scatter_mapbox(mapbox_style="open-street-map", **map_kwargs)

    # 마커 스타일링 및 레이아웃 설정
    fig.update_traces(marker=dict(size=12, opacity=0.85))
    fig.update_layout(
        template=plotly_template,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text="매장 구분",
    )

    # 지도 출력
    st.plotly_chart(fig, use_container_width=True)
