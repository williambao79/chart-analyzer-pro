import base64
import json
from typing import Any, Dict

import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Chart Analyzer Pro v2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main .block-container {max-width: 1100px; padding-top: 1.2rem; padding-bottom: 3rem;}
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #7c3aed 100%);
        color: white;
        border-radius: 22px;
        padding: 22px 20px;
        margin-bottom: 16px;
        box-shadow: 0 14px 30px rgba(15,23,42,0.18);
    }
    .hero h1 {margin: 0 0 6px 0; font-size: 30px;}
    .hero p {margin: 0; color: rgba(255,255,255,0.88); font-size: 15px;}
    .card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        margin-bottom: 14px;
    }
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 12px;
        height: 100%;
    }
    .metric-label {font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: 700; margin-bottom: 5px;}
    .metric-value {font-size: 20px; font-weight: 800; color: #0f172a; line-height: 1.2;}
    .small-note {
        background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a;
        border-radius: 14px; padding: 10px 12px; font-size: 14px; margin-bottom: 12px;
    }
    .pill {display:inline-block; padding:7px 12px; border-radius:999px; font-size:13px; font-weight:700; margin-right:8px; margin-bottom:8px;}
    .pill-green {background:#dcfce7; color:#166534;}
    .pill-yellow {background:#fef3c7; color:#92400e;}
    .pill-red {background:#fee2e2; color:#991b1b;}
    .pill-blue {background:#dbeafe; color:#1d4ed8;}
    .section-title {font-size: 21px; font-weight: 800; color: #0f172a; margin: 10px 0 10px 0;}
    div.stButton > button {border-radius: 14px; min-height: 46px; font-weight: 800;}
    div[data-testid="stFileUploader"] section {border-radius: 14px;}
    @media (max-width: 640px) {
        .hero h1 {font-size: 26px;}
        .main .block-container {padding-left: 0.8rem; padding-right: 0.8rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📊 Chart Analyzer Pro v2</h1>
        <p>Upload ảnh chart và app sẽ tự phân tích: trend, support/resistance, setup, entry, stop loss, target, risk/reward và quyết định cuối.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="small-note">
        Bản v2 tối ưu cho iPhone: upload chart → chọn kiểu phân tích → nhận Entry Zone, Stop Loss, Target và Final Decision. Nếu đã lưu API key trong Streamlit secrets, bạn không cần nhập key mỗi lần.
    </div>
    """,
    unsafe_allow_html=True,
)


def pill_class(decision: str) -> str:
    t = (decision or "").upper()
    if "WATCH TO ENTER" in t or "BUY" in t:
        return "pill pill-green"
    if "WAIT" in t or "BREAKOUT" in t or "PULLBACK" in t or "REVERSAL" in t or "CAUTION" in t:
        return "pill pill-yellow"
    if "NO TRADE" in t or "AVOID" in t or "RISK" in t:
        return "pill pill-red"
    return "pill pill-blue"


def safe_str(v: Any, default: str = "—") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


ANALYSIS_SCHEMA_EXAMPLE = {
    "ticker": "CIFR",
    "timeframe": "1D",
    "trend": "Uptrend / Downtrend / Mixed",
    "market_structure": "Higher highs and higher lows / lower highs / range / breakdown / breakout",
    "setup": "Near Support / Near Resistance / Breakout Watch / Pullback Watch / Reversal Setup / Middle Zone",
    "signal": "BUY WATCH / WAIT / AVOID",
    "final_decision": "WATCH TO ENTER / WAIT / NO TRADE / BREAKOUT WATCH / PULLBACK WATCH / REVERSAL WATCH",
    "support_zone": "60.20 - 61.00",
    "resistance_zone": "65.50 - 66.80",
    "entry_zone": "60.40 - 61.20",
    "aggressive_entry": "61.00 - 61.60",
    "deep_safe_entry": "58.90 - 60.00",
    "stop_loss": "58.40",
    "target_1": "64.50",
    "target_2": "67.20",
    "risk_reward": "2.1",
    "volume_read": "Above Average / Normal / Weak / Strong breakout volume",
    "momentum_read": "RSI healthy / overbought / oversold / MACD improving / weak momentum",
    "bull_case": ["Holding support", "Reclaiming moving averages", "Volume improves on bounce"],
    "bear_case": ["Loses support", "Weak close near lows", "Heavy sell volume"],
    "chart_notes": ["Short explanation 1", "Short explanation 2", "Short explanation 3"],
    "action_plan": "Wait for a green candle confirmation off support before entering.",
    "confidence": "High / Medium / Low",
    "disclaimer": "This is chart-based analysis only, not financial advice."
}


SYSTEM_PROMPT = f"""
You are a professional technical chart analyst. The user will upload a stock chart screenshot.
Your job is to analyze ONLY what can reasonably be inferred from the chart image and the optional metadata provided by the user.

Requirements:
- Focus on chart analysis only.
- Infer trend, support/resistance, setup quality, possible entry zones, stop loss, targets, and risk/reward.
- If exact prices are visible, use them. If some values are not clearly visible, estimate conservatively and say so implicitly in the notes.
- Be realistic, not overconfident.
- If the chart is low quality, mention that confidence is low.
- Avoid making up company fundamentals, news, or earnings unless the chart image itself explicitly shows them.
- Final decision must be one of: WATCH TO ENTER, WAIT, NO TRADE, BREAKOUT WATCH, PULLBACK WATCH, REVERSAL WATCH, CAUTION.
- Signal must be one of: BUY WATCH, WAIT, AVOID.
- Setup must be one of: Near Support, Near Resistance, Breakout Watch, Pullback Watch, Reversal Setup, Middle Zone.
- Keep all text concise and practical for a swing trader.

Return valid JSON only with the same keys as this example schema:
{json.dumps(ANALYSIS_SCHEMA_EXAMPLE, ensure_ascii=False)}
"""


def analyze_chart_image(
    image_bytes: bytes,
    mime_type: str,
    ticker: str,
    timeframe: str,
    style: str,
    extra_context: str,
    api_key: str,
) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    user_prompt = f"""
Analyze this uploaded chart screenshot.
Optional metadata from user:
- Ticker: {ticker or 'Unknown'}
- Timeframe: {timeframe or 'Auto detect'}
- Trading style: {style}
- Extra user context: {extra_context or 'None'}

Please read the chart carefully and return the JSON only.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                ],
            },
        ],
    )

    raw = response.output_text.strip()
    try:
        return json.loads(raw)
    except Exception:
        # try to extract JSON block if model added markdown fences
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)


def render_metric(label: str, value: str):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown("### ⚙️ Cài đặt")
    secret_key = ""
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        secret_key = ""

    if secret_key:
        st.success("API key đã được lưu trong Streamlit secrets.")
        api_key = secret_key
    else:
        with st.expander("Nhập API key", expanded=True):
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="Muốn khỏi nhập mỗi lần, lưu key trong Streamlit secrets với tên OPENAI_API_KEY.",
            )

    style = st.selectbox(
        "Phong cách phân tích",
        ["Swing trade", "Day trade", "Position trade", "Conservative swing", "Aggressive breakout"],
        index=0,
    )
    st.caption("Khuyến nghị: dùng chart rõ, có nến + volume + timeframe. Chart càng rõ thì kết quả càng tốt.")

left, right = st.columns([1, 1])

with left:
    st.markdown('<div class="section-title">Upload chart</div>', unsafe_allow_html=True)
    st.caption("Bước 1: Upload ảnh chart. Bước 2: nhập ticker/timeframe nếu biết. Bước 3: bấm Analyze Chart.")
    uploaded_file = st.file_uploader("Upload chart image", type=["png", "jpg", "jpeg", "webp"])
    ticker = st.text_input("Ticker (optional)", placeholder="VD: CIFR, KTOS, SOUN")
    timeframe = st.selectbox(
        "Timeframe",
        ["Auto detect", "1m", "5m", "15m", "1h", "4h", "1D", "1W"],
        index=0,
    )
    extra_context = st.text_area(
        "Context thêm (optional)",
        placeholder="VD: Tôi muốn phân tích theo kiểu swing trade, đang quan tâm điểm vào đẹp...",
        height=110,
    )
    analyze_btn = st.button("📈 Analyze Chart", type="primary", use_container_width=True)

with right:
    st.markdown('<div class="section-title">Preview</div>', unsafe_allow_html=True)
    if uploaded_file is not None:
        st.image(uploaded_file, use_container_width=True)
    else:
        st.info("Upload chart để xem preview ở đây.")

if "chart_analysis_result" not in st.session_state:
    st.session_state.chart_analysis_result = None

if analyze_btn:
    if uploaded_file is None:
        st.error("Bạn chưa upload chart.")
    elif not api_key:
        st.error("Bạn chưa nhập OpenAI API key.")
    else:
        try:
            with st.spinner("Đang phân tích chart..."):
                result = analyze_chart_image(
                    image_bytes=uploaded_file.getvalue(),
                    mime_type=uploaded_file.type or "image/png",
                    ticker=ticker.strip().upper(),
                    timeframe=timeframe,
                    style=style,
                    extra_context=extra_context,
                    api_key=api_key,
                )
            st.session_state.chart_analysis_result = result
        except Exception as e:
            st.error(f"Lỗi khi phân tích chart: {e}")

result = st.session_state.chart_analysis_result

if result:
    st.markdown('<div class="section-title">Kết quả phân tích</div>', unsafe_allow_html=True)

    decision = safe_str(result.get("final_decision"))
    signal = safe_str(result.get("signal"))
    confidence = safe_str(result.get("confidence"))
    st.markdown(
        f'<span class="{pill_class(decision)}">{decision}</span>'
        f'<span class="pill pill-blue">Signal: {signal}</span>'
        f'<span class="pill pill-blue">Confidence: {confidence}</span>',
        unsafe_allow_html=True,
    )

    row1 = st.columns(4)
    with row1[0]:
        render_metric("Trend", safe_str(result.get("trend")))
    with row1[1]:
        render_metric("Setup", safe_str(result.get("setup")))
    with row1[2]:
        render_metric("Support", safe_str(result.get("support_zone")))
    with row1[3]:
        render_metric("Resistance", safe_str(result.get("resistance_zone")))

    row2 = st.columns(4)
    with row2[0]:
        render_metric("Entry Zone", safe_str(result.get("entry_zone")))
    with row2[1]:
        render_metric("Aggressive Entry", safe_str(result.get("aggressive_entry")))
    with row2[2]:
        render_metric("Deep Safe Entry", safe_str(result.get("deep_safe_entry")))
    with row2[3]:
        render_metric("Stop Loss", safe_str(result.get("stop_loss")))

    row3 = st.columns(4)
    with row3[0]:
        render_metric("Target 1", safe_str(result.get("target_1")))
    with row3[1]:
        render_metric("Target 2", safe_str(result.get("target_2")))
    with row3[2]:
        render_metric("Risk / Reward", safe_str(result.get("risk_reward")))
    with row3[3]:
        render_metric("Timeframe", safe_str(result.get("timeframe")))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Market Structure**")
        st.write(safe_str(result.get("market_structure")))
        st.markdown("**Volume Read**")
        st.write(safe_str(result.get("volume_read")))
        st.markdown("**Momentum Read**")
        st.write(safe_str(result.get("momentum_read")))
        st.markdown("**Action Plan**")
        st.write(safe_str(result.get("action_plan")))
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Bull Case**")
        for item in result.get("bull_case", []) or []:
            st.write(f"- {item}")
        st.markdown("**Bear Case**")
        for item in result.get("bear_case", []) or []:
            st.write(f"- {item}")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**Chart Notes**")
    notes = result.get("chart_notes", []) or []
    if notes:
        for note in notes:
            st.write(f"- {note}")
    else:
        st.write("—")
    st.markdown("**Disclaimer**")
    st.caption(safe_str(result.get("disclaimer"), "This is chart-based analysis only, not financial advice."))
    st.markdown('</div>', unsafe_allow_html=True)

    st.download_button(
        "⬇️ Download analysis JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name=f"chart_analysis_{safe_str(result.get('ticker'), 'chart')}.json",
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("Raw JSON"):
        st.json(result)
