import os
import folium
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

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

# 테마에 따른 CSS 스타일 및 지도/차트 템플릿 적용
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
    folium_tiles = "CartoDB dark_matter"
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
    folium_tiles = "OpenStreetMap"
    plotly_template = "plotly_white"

# ==========================================
# 3. 타이틀 표시
# ==========================================
st.title("🏪 편의점 & 카페 위치 안내 지도")
st.caption(
    "시/도 및 동별 분류 선택, 특정 매장 기준 반경 내 매장 검색 기능 및 통계 차트를 제공합니다."
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
# 8. 메인 화면 - Folium 지도 (아이콘 마커)
# ==========================================
if df_filtered.empty:
    st.info("조건에 일치하는 매장이 없습니다. 검색 조건이나 반경을 변경해보세요.")
else:
    if use_radius_search and selected_center_store is not None:
        center_lat = selected_center_store["위도"]
        center_lon = selected_center_store["경도"]
        zoom_level = 14
    else:
        center_lat = df_filtered["위도"].mean()
        center_lon = df_filtered["경도"].mean()
        zoom_level = 13 if selected_dong != "전체" else 11

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_level,
        tiles=folium_tiles,
    )

    marker_cluster = MarkerCluster().add_to(m)

    for _, row in df_filtered.iterrows():
        is_cafe = row["상권업종소분류명"] == "카페"
        icon_name = "coffee" if is_cafe else "shopping-cart"
        icon_color = "orange" if is_cafe else "blue"
        category_text = "☕ 카페" if is_cafe else "🏪 편의점"

        folium.Marker(
            location=[row["위도"], row["경도"]],
            popup=f"<b>{row['상호명']}</b><br>업종: {category_text}<br>동: {row['동명']}",
            tooltip=f"{row['상호명']} ({category_text})",
            icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
        ).add_to(marker_cluster)

    st_folium(m, width="100%", height=550, returned_objects=[])

    st.markdown("---")

    # ==========================================
    # 9. 지도 하단 - 통계 막대 그래프 시각화
    # ==========================================
    st.header("📊 매장 통계 분석")

    chart_col1, chart_col2 = st.columns(2)

    # 1) 편의점 vs 카페 수 비교 막대 그래프
    with chart_col1:
        st.subheader("🏪 편의점 vs ☕ 카페 비율")
        category_counts = (
            df_filtered["상권업종소분류명"].value_counts().reset_index()
        )
        category_counts.columns = ["업종", "매장수"]

        fig_type = px.bar(
            category_counts,
            x="업종",
            y="매장수",
            color="업종",
            color_discrete_map={
                "편의점": "#1f77b4"
                if st.session_state.theme_mode == "light"
                else "#00d2ff",
                "카페": "#ff7f0e"
                if st.session_state.theme_mode == "light"
                else "#ff9f43",
            },
            text="매장수",
            height=400,
        )
        fig_type.update_traces(
            texttemplate="%{text:,}개", textposition="outside"
        )
        fig_type.update_layout(
            template=plotly_template,
            xaxis_title="",
            yaxis_title="매장 수 (개)",
            showlegend=False,
        )
        st.plotly_chart(fig_type, use_container_width=True)

    # 2) 동별 카페 수 순위 막대 그래프 (Top 15)
    with chart_col2:
        st.subheader("☕ 동별 카페 수 현황 (Top 15)")

        # 카페 데이터만 필터링 후 동별 집계
        cafe_df = df_filtered[df_filtered["상권업종소분류명"] == "카페"]

        if cafe_df.empty:
            st.info("선택된 조건 내에 카페가 존재하지 않습니다.")
        else:
            dong_cafe_counts = (
                cafe_df["동명"].value_counts().head(15).reset_index()
            )
            dong_cafe_counts.columns = ["동명", "카페수"]

            fig_dong_cafe = px.bar(
                dong_cafe_counts,
                x="동명",
                y="카페수",
                color_discrete_sequence=["#ff7f0e" if st.session_state.theme_mode == "light" else "#ff9f43"],
                text="카페수",
                height=400,
            )
            fig_dong_cafe.update_traces(
                texttemplate="%{text:,}개", textposition="outside"
            )
            fig_dong_cafe.update_layout(
                template=plotly_template,
                xaxis_title="동 이름",
                yaxis_title="카페 수 (개)",
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_dong_cafe, use_container_width=True)
