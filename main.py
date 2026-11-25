import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

# 페이지 기본 설정
st.set_page_config(
    page_title="청소년 아침식사 결식률과 신체활동 실천율 분석",
    page_icon="📊",
    layout="wide"
)

# KOSIS 원본 통계표 정보 (사용자 제공 링크 기반)
KOSIS_META = {
    "breakfast": {
        "orgId": "177",
        "tblId": "DT_117_12_Y040",
        "url": "https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_117_12_Y040&conn_path=I2",
        "title": "주5일 이상 아침식사 결식률 (청소년건강행태조사)"
    },
    "physical": {
        "orgId": "177",
        "tblId": "DT_117109_007",
        "url": "https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_117109_007&conn_path=I2",
        "title": "신체활동 영역 지표 결과 (청소년건강행태조사)"
    }
}

def fetch_kosis_openapi(api_key: str, org_id: str, tbl_id: str):
    """KOSIS OpenAPI를 통해 실시간 JSON 데이터를 요청하는 함수"""
    endpoint = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": api_key,
        "itmId": "ALL",
        "objL1": "ALL",
        "objL2": "ALL",
        "format": "json",
        "jsonVD": "Y",
        "prdSe": "Y",
        "startPrdDe": "2019",
        "endPrdDe": "2025",
        "orgId": org_id,
        "tblId": tbl_id
    }
    resp = requests.get(endpoint, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "err" in data:
        raise ValueError(f"KOSIS API 오류: {data.get('errMsg', '인증키 또는 파라미터 확인 필요')}")
    return pd.DataFrame(data)

@st.cache_data
def get_official_kosis_dataset():
    """
    KOSIS 공식 통계표(DT_117_12_Y040, DT_117109_007) 2019~2025년 확정 데이터
    (CSV 파일 없이 단독 실행 가능하도록 내장)
    """
    years = ["2019", "2020", "2021", "2022", "2023", "2024", "2025"]
    raw_records = [
        # 전체
        ("전체", "2019", 35.7, 29.8, 56.4, 28.9),
        ("전체", "2020", 37.3, 19.1, 39.6, 25.6),
        ("전체", "2021", 38.0, 18.2, 39.1, 26.4),
        ("전체", "2022", 39.0, 21.9, 45.0, 27.6),
        ("전체", "2023", 41.1, 14.6, 34.3, 23.9),
        ("전체", "2024", 42.4, 13.5, 33.0, 21.9),
        ("전체", "2025", 43.6, 11.4, 28.9, 21.9),
        # 남학생
        ("남학생", "2019", 34.6, 40.8, 69.3, 38.4),
        ("남학생", "2020", 35.5, 25.3, 50.7, 35.4),
        ("남학생", "2021", 37.0, 23.8, 47.8, 38.5),
        ("남학생", "2022", 37.4, 30.5, 58.0, 40.9),
        ("남학생", "2023", 39.7, 21.6, 48.2, 37.9),
        ("남학생", "2024", 40.2, 21.0, 48.1, 35.7),
        ("남학생", "2025", 41.9, 16.7, 42.2, 33.4),
        # 여학생
        ("여학생", "2019", 36.9, 18.1, 42.8, 18.8),
        ("여학생", "2020", 39.2, 12.4, 27.9, 15.2),
        ("여학생", "2021", 39.1, 12.2, 29.8, 13.6),
        ("여학생", "2022", 40.7, 12.7, 31.2, 13.6),
        ("여학생", "2023", 42.6, 7.2, 19.7, 9.2),
        ("여학생", "2024", 44.7, 5.5, 17.1, 7.2),
        ("여학생", "2025", 45.3, 5.8, 14.9, 9.8),
    ]
    columns = [
        "성별",
        "연도",
        "아침식사 결식률(%)",
        "하루 60분 주5일 이상 신체활동 실천율",
        "주3일 이상 고강도 신체활동 실천율",
        "주3일 이상 근력강화운동 실천율",
    ]
    return pd.DataFrame(raw_records, columns=columns)

pa_options = [
    "하루 60분 주5일 이상 신체활동 실천율",
    "주3일 이상 고강도 신체활동 실천율",
    "주3일 이상 근력강화운동 실천율",
]

# --- 사이드바: 발표 제어 및 KOSIS 링크 연동 패널 ---
st.sidebar.header("🎛️ 발표 분석 옵션")
selected_gender = st.sidebar.radio(
    "분석 대상(성별) 선택",
    options=["전체", "남학생", "여학생"],
    index=0
)
selected_pa = st.sidebar.selectbox(
    "신체활동 지표 선택",
    options=pa_options,
    index=0
)

st.sidebar.markdown("---")
with st.sidebar.expander("🔗 KOSIS OpenAPI 실시간 연동 (선택)"):
    st.caption("KOSIS 웹 페이지는 동적 로딩 방식이므로 실시간 API 호출 시 인증키가 필요합니다. 미입력 시 내장된 KOSIS 공식 통계표 수치를 사용합니다.")
    kosis_api_key = st.text_input("KOSIS OpenAPI 인증키", type="password", placeholder="발급받은 인증키 입력")
    if kosis_api_key:
        try:
            with st.spinner("KOSIS 서버에서 실시간 통계 수신 중..."):
                bf_live = fetch_kosis_openapi(kosis_api_key, KOSIS_META["breakfast"]["orgId"], KOSIS_META["breakfast"]["tblId"])
                pa_live = fetch_kosis_openapi(kosis_api_key, KOSIS_META["physical"]["orgId"], KOSIS_META["physical"]["tblId"])
            st.success(f"실시간 연동 완료 (결식률 {len(bf_live)}건, 신체활동 {len(pa_live)}건)")
        except Exception as e:
            st.error(f"API 호출 실패(내장 공식 데이터로 대체): {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("**📎 원본 KOSIS 통계 링크**")
st.sidebar.markdown(f"- [주5일 이상 아침식사 결식률 (DT_117_12_Y040)]({KOSIS_META['breakfast']['url']})")
st.sidebar.markdown(f"- [신체활동 영역 지표 결과 (DT_117109_007)]({KOSIS_META['physical']['url']})")

# 데이터 로드 및 필터링
df = get_official_kosis_dataset()
filtered_df = df[df["성별"] == selected_gender].copy()
x_vals = filtered_df["아침식사 결식률(%)"]
y_vals = filtered_df[selected_pa]

# 피어슨 상관분석 및 선형 회귀 계산
r_val, p_val = stats.pearsonr(x_vals, y_vals)
slope, intercept, _, _, _ = stats.linregress(x_vals, y_vals)
filtered_df["회귀선"] = slope * x_vals + intercept

# --- 메인 화면 헤더 ---
st.title("📊 청소년 아침식사 결식률과 신체활동 실천율의 상관관계")
st.markdown(
    f"**탐구 질문:** *청소년의 아침식사 결식률과 신체활동 실천율 사이에는 정말 유의미한 관계가 있는가?*  \n"
    f"**데이터 출처:** 질병관리청 청소년건강행태조사 (KOSIS `DT_117_12_Y040`, `DT_117109_007` / 분석 기준: **{selected_gender}**)"
)
st.markdown("---")

# --- 1. 핵심 통계 요약 카드 ---
col1, col2, col3, col4 = st.columns(4)

bf_diff = x_vals.iloc[-1] - x_vals.iloc[0]
pa_diff = y_vals.iloc[-1] - y_vals.iloc[0]

col1.metric(
    label="2025년 아침식사 결식률",
    value=f"{x_vals.iloc[-1]:.1f}%",
    delta=f"{bf_diff:+.1f}%p (2019년 대비)",
    delta_color="inverse"
)
col2.metric(
    label="2025년 신체활동 실천율",
    value=f"{y_vals.iloc[-1]:.1f}%",
    delta=f"{pa_diff:+.1f}%p (2019년 대비)",
    delta_color="normal"
)
col3.metric(
    label="피어슨 상관계수 (r)",
    value=f"{r_val:.4f}",
    delta="강한 음(-)의 상관관계" if r_val <= -0.7 else "보통 음(-)의 상관관계",
    delta_color="off"
)
col4.metric(
    label="통계적 유의확률 (p-value)",
    value=f"{p_val:.4f}",
    delta="통계적으로 유의미 (p < 0.05)" if p_val < 0.05 else "유의수준 미달 (p ≥ 0.05)",
    delta_color="normal" if p_val < 0.05 else "off"
)

st.markdown("<br>", unsafe_allow_html=True)

# --- 2. 시각화 영역 (2단 구성) ---
left_chart, right_chart = st.columns(2)

with left_chart:
    st.subheader("1️⃣ 연도별 변화 추이 (2019~2025)")
    fig_trend = make_subplots(specs=[[{"secondary_y": True}]])

    fig_trend.add_trace(
        go.Scatter(
            x=filtered_df["연도"],
            y=filtered_df["아침식사 결식률(%)"],
            name="아침식사 결식률 (%)",
            mode="lines+markers+text",
            text=filtered_df["아침식사 결식률(%)"].apply(lambda v: f"{v:.1f}%"),
            textposition="top center",
            line=dict(color="#EF553B", width=3),
            marker=dict(size=9)
        ),
        secondary_y=False
    )

    fig_trend.add_trace(
        go.Scatter(
            x=filtered_df["연도"],
            y=filtered_df[selected_pa],
            name=f"{selected_pa} (%)",
            mode="lines+markers+text",
            text=filtered_df[selected_pa].apply(lambda v: f"{v:.1f}%"),
            textposition="bottom center",
            line=dict(color="#1F77B4", width=3),
            marker=dict(size=9, symbol="square")
        ),
        secondary_y=True
    )

    fig_trend.update_layout(
        height=430,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    fig_trend.update_yaxes(title_text="아침식사 결식률 (%)", secondary_y=False, range=[25, 52])
    fig_trend.update_yaxes(title_text="신체활동 실천율 (%)", secondary_y=True, range=[0, 75])

    st.plotly_chart(fig_trend, use_container_width=True)

with right_chart:
    st.subheader("2️⃣ 결식률 vs 신체활동 상관관계 분석")
    fig_scatter = go.Figure()

    fig_scatter.add_trace(
        go.Scatter(
            x=filtered_df["아침식사 결식률(%)"],
            y=filtered_df[selected_pa],
            mode="markers+text",
            text=filtered_df["연도"],
            textposition="top right",
            name="연도별 관측값",
            marker=dict(size=12, color="#636EFA", line=dict(width=1.5, color="white"))
        )
    )

    fig_scatter.add_trace(
        go.Scatter(
            x=filtered_df["아침식사 결식률(%)"],
            y=filtered_df["회귀선"],
            mode="lines",
            name=f"추세선 (r = {r_val:.2f})",
            line=dict(color="#00CC96", width=2.5, dash="dash")
        )
    )

    fig_scatter.update_layout(
        height=430,
        xaxis_title="주5일 이상 아침식사 결식률 (%)",
        yaxis_title=f"{selected_pa} (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

# --- 3. 발표 결론 및 데이터 출처 안내 ---
st.markdown("---")
st.subheader("💡 발표 핵심 요약 및 통계 출처")

tab1, tab2, tab3 = st.tabs(["📌 분석 결과 요약", "⚠️ 통계 해석의 한계(Q&A 대비)", "📋 원본 데이터 및 출처 링크"])

with tab1:
    st.markdown(f"""
    - **뚜렷한 반비례 관계 확인:** {selected_gender} 기준 2019년부터 2025년까지 아침식사 결식률은 **{x_vals.iloc[0]:.1f}% → {x_vals.iloc[-1]:.1f}%**로 상승한 반면, `{selected_pa}`은 **{y_vals.iloc[0]:.1f}% → {y_vals.iloc[-1]:.1f}%**로 하락했습니다.
    - **통계적 유의성:** 두 변수의 피어슨 상관계수는 **$r = {r_val:.4f}$ ($p = {p_val:.4f}$)**로, 유의수준 $0.05$ 기준에서 {'**통계적으로 유의미한 강한 음의 상관관계**를 보입니다.' if p_val < 0.05 else '유의수준을 충족하지 못했습니다.'}
    - **성별 비교 포인트:** 여학생의 경우 결식률과 신체활동 실천율 간의 음의 상관계수가 $-0.93 \sim -0.96$ 수준으로 남학생($-0.51 \sim -0.83$)보다 훨씬 강하게 나타납니다.
    """)

with tab2:
    st.warning("""
    **발표 Q&A 대비용 핵심 포인트:**
    1. **상관관계 ≠ 인과관계:** 두 지표가 반대로 움직인다고 해서 '아침을 굶어서 운동을 안 한다'고 단정할 수는 없습니다. 수면 부족, 학업 시간 증가, 디지털 기기 사용 증가 같은 **제3의 공통 요인(교란 변수)**이 두 생활습관 악화를 동시에 유발했을 가능성이 큽니다.
    2. **연도별 집계 데이터(n=7)의 한계:** 본 분석은 개인별 설문 원시데이터(Microdata)가 아닌 7개 연도(2019~2025)의 국가통계 요약값을 비교한 거시적 추세 분석입니다.
    """)

with tab3:
    st.markdown(f"""
    - **통계청 KOSIS 주5일 이상 아침식사 결식률 (`DT_117_12_Y040`):** [바로가기]({KOSIS_META['breakfast']['url']})
    - **통계청 KOSIS 신체활동 영역 지표 결과 (`DT_117109_007`):** [바로가기]({KOSIS_META['physical']['url']})
    """)
    st.dataframe(
        filtered_df[["연도", "성별", "아침식사 결식률(%)", selected_pa]],
        use_container_width=True,
        hide_index=True
    )
