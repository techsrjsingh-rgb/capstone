"""
app.py — Streamlit Dashboard for Fraud Detection AI Agent
==========================================================
Run with:  streamlit run frontend/app.py
"""

import json
import time
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

from core.data import SAMPLE_TRANSACTIONS
from core.rules import FraudDetectionRules
from core.graph import build_fraud_graph, get_graph_stats, to_cypher_export
from orchestrator.agent import FraudDetectionOrchestrator
from config.settings import config

K6_REPORT = Path("reports/k6_summary.json")

# ── Page config (must be first Streamlit call) ─────────────────────
st.set_page_config(
    page_title="Fraud Detection AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for a polished look ─────────────────────────────────
st.markdown("""
<style>
/* ── Global font & background ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 1.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.hero h1 { color: #ffffff; font-size: 2.4rem; font-weight: 700; margin: 0; }
.hero p  { color: #a8c0cc; font-size: 1.05rem; margin-top: 0.5rem; }

/* ── Metric cards ── */
.metric-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    border: 1px solid #2a2a4a;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}
.metric-card .label { color: #8899aa; font-size: 0.8rem; font-weight: 600;
                       text-transform: uppercase; letter-spacing: 1px; }
.metric-card .value { color: #ffffff; font-size: 2rem; font-weight: 700;
                       margin-top: 0.2rem; }
.metric-card.safe    { border-top: 4px solid #00e676; }
.metric-card.susp    { border-top: 4px solid #ffd600; }
.metric-card.high    { border-top: 4px solid #ff1744; }
.metric-card.total   { border-top: 4px solid #448aff; }

/* ── Risk badge pill ── */
.badge {
    display: inline-block; padding: 4px 14px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px;
}
.badge-safe   { background:#e8f5e9; color:#1b5e20; }
.badge-susp   { background:#fff3e0; color:#e65100; }
.badge-high   { background:#ffebee; color:#b71c1c; }

/* ── Result verdict banner ── */
.verdict {
    border-radius: 14px; padding: 1.5rem 2rem;
    text-align: center; margin: 1rem 0;
    font-size: 1.6rem; font-weight: 700;
}
.verdict-safe   { background: linear-gradient(135deg,#1b5e20,#2e7d32); color:#fff; }
.verdict-susp   { background: linear-gradient(135deg,#e65100,#f57c00); color:#fff; }
.verdict-high   { background: linear-gradient(135deg,#b71c1c,#d32f2f); color:#fff; }

/* ── Info box ── */
.info-box {
    background: #0d1b2a; border-left: 4px solid #448aff;
    border-radius: 8px; padding: 1rem 1.2rem; margin: 0.5rem 0;
    color: #c8d8e8; font-size: 0.9rem;
}
.warn-box {
    background: #1a1400; border-left: 4px solid #ffd600;
    border-radius: 8px; padding: 1rem 1.2rem; margin: 0.5rem 0;
    color: #ffe082; font-size: 0.9rem;
}
.danger-box {
    background: #1a0000; border-left: 4px solid #ff1744;
    border-radius: 8px; padding: 1rem 1.2rem; margin: 0.5rem 0;
    color: #ff8a80; font-size: 0.9rem;
}

/* ── Sidebar polish ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2027 0%, #1a1a2e 100%);
}
[data-testid="stSidebar"] * { color: #c8d8e8 !important; }

/* ── Tab styling ── */
[data-baseweb="tab-list"] { gap: 4px; }
[data-baseweb="tab"] {
    border-radius: 8px 8px 0 0 !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
}

/* ── Button ── */
[data-testid="stButton"] button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
}

/* ── Progress bar color ── */
[data-testid="stProgressBar"] > div > div { background-color: #448aff !important; }

/* ── Section divider ── */
.section-title {
    font-size: 1.1rem; font-weight: 700; color: #cce0f5;
    border-bottom: 2px solid #2a3a4a; padding-bottom: 0.4rem;
    margin: 1.2rem 0 0.8rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Color & icon maps ──────────────────────────────────────────────
RISK_COLORS = {"Safe": "#00e676", "Suspicious": "#ffd600", "High Risk": "#ff1744"}
RISK_BG     = {"Safe": "#e8f5e9", "Suspicious": "#fff9c4", "High Risk": "#ffebee"}
RISK_ICONS  = {"Safe": "✅", "Suspicious": "⚠️", "High Risk": "🚨"}
RISK_CLASS  = {"Safe": "safe", "Suspicious": "susp", "High Risk": "high"}

# ──────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────

def _rules_only_result(txn: dict, rules: FraudDetectionRules) -> dict:
    result = rules.evaluate(txn, SAMPLE_TRANSACTIONS)
    return {
        "transaction_id":     txn["transaction_id"],
        "risk_level":         result["risk_level"],
        "fraud_reasons":      result["fraud_reasons"],
        "risk_score":         result["risk_score"],
        "explanation":        _simple_explanation(result),
        "recommended_action": _simple_action(result["risk_level"]),
        "confidence":         0.9,
        "agent_trace":        [{"agent": "RulesAgent (no AI)", "result": result["risk_level"]}],
        "correlation_id":     "rules-only",
    }

def _simple_explanation(result: dict) -> str:
    icon  = RISK_ICONS.get(result["risk_level"], "⚠️")
    lines = [f"**{result['transaction_id']} — {icon} {result['risk_level']}**", ""]
    if result["fraud_reasons"]:
        lines.append("Fraud indicators detected:")
        for r in result["fraud_reasons"]:
            lines.append(f"  • {r}")
    else:
        lines.append("No fraud indicators detected. Transaction is safe.")
    lines.append(f"\nRisk Score: {result['risk_score']:.0f}/100")
    return "\n".join(lines)

def _simple_action(risk_level: str) -> str:
    return {"Safe": "none", "Suspicious": "alert_customer",
            "High Risk": "block_transaction"}.get(risk_level, "monitor")

def _results_to_df(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        txn_id = r.get("transaction_id", "?")
        orig   = next((t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == txn_id), {})
        rows.append({
            "transaction_id":    txn_id,
            "customer_id":       orig.get("customer_id", "?"),
            "amount":            float(orig.get("amount", 0)),
            "amount_fmt":        f"₹{float(orig.get('amount', 0)):,.0f}",
            "location":          orig.get("location", "?"),
            "transaction_type":  orig.get("transaction_type", "?"),
            "risk_level":        r.get("risk_level", "Suspicious"),
            "risk_score":        r.get("risk_score", 0),
            "fraud_reason_short": "; ".join(r.get("fraud_reasons", []))[:60] or "—",
        })
    return pd.DataFrame(rows)

def _metric_card(label: str, value, card_class: str = "total") -> str:
    return f"""
    <div class="metric-card {card_class}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
    </div>"""

def _verdict_html(risk: str, icon: str, score: float) -> str:
    cls = {"Safe": "verdict-safe", "Suspicious": "verdict-susp",
           "High Risk": "verdict-high"}.get(risk, "verdict-susp")
    return f'<div class="verdict {cls}">{icon} {risk.upper()} &nbsp;·&nbsp; Risk Score: {score:.0f}/100</div>'

# ──────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Fraud Detection AI")
    st.markdown("---")

    api_ok = bool(config.ANTHROPIC_API_KEY)

    st.markdown("### ⚙️ System Status")
    st.markdown(f"**AI Agent:** {'🟢 Connected' if api_ok else '🔴 No API Key'}")
    st.markdown(f"**Transactions:** {len(SAMPLE_TRANSACTIONS)} loaded")
    st.markdown(f"**Primary Model:** `{config.PRIMARY_MODEL}`")
    st.markdown(f"**Fallback Model:** `{config.FALLBACK_MODEL}`")

    st.markdown("---")
    st.markdown("### 🔧 Fraud Thresholds")
    st.markdown(f"💰 **High Amount:** ₹{config.HIGH_AMOUNT_THRESHOLD:,.0f}")
    st.markdown(f"⏱️ **Rapid Window:** {config.RAPID_TXN_WINDOW_SEC // 60} minutes")
    st.markdown(f"🔢 **Rapid Count:** {config.RAPID_TXN_COUNT}+ transactions")

    st.markdown("---")
    st.markdown("### 📋 Four Fraud Rules")
    st.markdown("""
- 💸 Very high amount
- 📍 Unusual location
- ⚡ Multiple rapid txns
- 🌍 International txn
""")

    st.markdown("---")
    use_ai = st.checkbox(
        "🤖 Use AI Agent",
        value=api_ok,
        help="Uncheck for fast rule-only mode (no API key needed)",
    )
    st.markdown("---")
    st.caption("© 2026 Fraud Detection AI Capstone")

# ──────────────────────────────────────────────────────────────────
# HERO BANNER
# ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🛡️ Fraud Detection AI Agent</h1>
  <p>Multi-agent AI system · Analyzes banking transactions in real time ·
     Classifies as ✅ Safe &nbsp;·&nbsp; ⚠️ Suspicious &nbsp;·&nbsp; 🚨 High Risk</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────────────
tab_batch, tab_single, tab_load, tab_graph, tab_about = st.tabs([
    "📊 Batch Analysis", "🔎 Analyze Transaction",
    "⚡ Load Tests", "🕸️ Transaction Graph", "ℹ️ About",
])

# ══════════════════════════════════════════════════════════════════
# TAB 1 — BATCH ANALYSIS
# ══════════════════════════════════════════════════════════════════
with tab_batch:
    st.markdown('<div class="section-title">Analyze All Sample Transactions</div>',
                unsafe_allow_html=True)
    st.markdown(f"Run fraud detection on all **{len(SAMPLE_TRANSACTIONS)}** sample transactions at once.")

    col_btn, col_clear, _ = st.columns([1, 1, 6])
    run_clicked   = col_btn.button("▶️ Run Analysis", type="primary")
    clear_clicked = col_clear.button("🗑️ Clear")

    if clear_clicked:
        for key in ["batch_results", "batch_df"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if run_clicked:
        results      = []
        rules_engine = FraudDetectionRules()
        if use_ai and api_ok:
            orchestrator = FraudDetectionOrchestrator()

        progress = st.progress(0, text="Starting analysis…")

        for i, txn in enumerate(SAMPLE_TRANSACTIONS):
            if use_ai and api_ok:
                try:
                    result = orchestrator.analyze(txn, SAMPLE_TRANSACTIONS)
                except Exception as e:
                    result = _rules_only_result(txn, rules_engine)
                    result["error"] = str(e)
            else:
                result = _rules_only_result(txn, rules_engine)

            results.append(result)
            progress.progress(
                (i + 1) / len(SAMPLE_TRANSACTIONS),
                text=f"Analyzed {i + 1} / {len(SAMPLE_TRANSACTIONS)} transactions"
            )
            time.sleep(0.05)

        progress.empty()
        st.session_state["batch_results"] = results
        st.session_state["batch_df"]      = _results_to_df(results)
        st.success(f"✅ Analysis complete! {len(results)} transactions processed.")

    if "batch_results" in st.session_state:
        results = st.session_state["batch_results"]
        df      = st.session_state["batch_df"]

        safe_count  = sum(1 for r in results if r.get("risk_level") == "Safe")
        susp_count  = sum(1 for r in results if r.get("risk_level") == "Suspicious")
        high_count  = sum(1 for r in results if r.get("risk_level") == "High Risk")

        # ── Metric cards ──────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(_metric_card("Total Analyzed", len(results), "total"),
                    unsafe_allow_html=True)
        c2.markdown(_metric_card("✅ Safe", safe_count, "safe"),
                    unsafe_allow_html=True)
        c3.markdown(_metric_card("⚠️ Suspicious", susp_count, "susp"),
                    unsafe_allow_html=True)
        c4.markdown(_metric_card("🚨 High Risk", high_count, "high"),
                    unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Charts ────────────────────────────────────────────────
        st.markdown('<div class="section-title">📈 Visual Analytics</div>',
                    unsafe_allow_html=True)
        chart_col1, chart_col2, chart_col3 = st.columns(3)

        with chart_col1:
            # Donut chart
            counts = df["risk_level"].value_counts().reset_index()
            counts.columns = ["Risk Level", "Count"]
            fig_pie = px.pie(
                counts, names="Risk Level", values="Count",
                color="Risk Level",
                color_discrete_map=RISK_COLORS,
                hole=0.55,
                title="Risk Distribution",
            )
            fig_pie.update_traces(textinfo="value+percent",
                                   textfont_size=13,
                                   marker=dict(line=dict(color="#1a1a2e", width=2)))
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#c8d8e8",
                title_font_size=15,
                showlegend=True,
                legend=dict(font=dict(color="#c8d8e8")),
                margin=dict(t=40, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with chart_col2:
            # Bar chart — amounts by risk
            fig_bar = px.bar(
                df.sort_values("amount", ascending=False),
                x="transaction_id", y="amount",
                color="risk_level",
                color_discrete_map=RISK_COLORS,
                title="Transaction Amounts",
                labels={"amount": "Amount (₹)", "transaction_id": "Transaction"},
            )
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                font_color="#c8d8e8",
                title_font_size=15,
                xaxis=dict(tickangle=-45, gridcolor="#2a3a4a"),
                yaxis=dict(gridcolor="#2a3a4a"),
                showlegend=False,
                margin=dict(t=40, b=80, l=10, r=10),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with chart_col3:
            # Risk score histogram
            fig_hist = px.histogram(
                df, x="risk_score", color="risk_level",
                color_discrete_map=RISK_COLORS,
                nbins=10,
                title="Risk Score Spread",
                labels={"risk_score": "Risk Score", "count": "Count"},
            )
            fig_hist.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                font_color="#c8d8e8",
                title_font_size=15,
                xaxis=dict(gridcolor="#2a3a4a"),
                yaxis=dict(gridcolor="#2a3a4a"),
                showlegend=False,
                margin=dict(t=40, b=10, l=10, r=10),
                bargap=0.1,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("---")

        # ── Results table ─────────────────────────────────────────
        st.markdown('<div class="section-title">📋 Transaction Results</div>',
                    unsafe_allow_html=True)

        def _row_color(row):
            bg = {"Safe": "#e8f5e9", "Suspicious": "#fff9c4",
                  "High Risk": "#ffebee"}.get(row["Risk Level"], "")
            return [f"background-color: {bg}; color: #111"] * len(row)

        display_df = df[[
            "transaction_id", "customer_id", "amount_fmt",
            "location", "transaction_type", "risk_level",
            "risk_score", "fraud_reason_short"
        ]].copy()
        display_df.columns = [
            "Transaction ID", "Customer", "Amount",
            "Location", "Type", "Risk Level", "Risk Score", "Fraud Reason",
        ]

        st.dataframe(
            display_df.style.apply(_row_color, axis=1),
            use_container_width=True,
            height=420,
        )

        # ── Expandable transaction details ────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-title">🔍 Transaction Details</div>',
                    unsafe_allow_html=True)

        # Filter bar
        filter_col, _ = st.columns([1, 3])
        risk_filter = filter_col.selectbox(
            "Filter by Risk Level", ["All", "High Risk", "Suspicious", "Safe"]
        )

        filtered = results if risk_filter == "All" else [
            r for r in results if r.get("risk_level") == risk_filter
        ]

        for result in filtered:
            txn_id = result.get("transaction_id", "?")
            risk   = result.get("risk_level", "Suspicious")
            icon   = RISK_ICONS.get(risk, "⚠️")
            score  = result.get("risk_score", 0)
            color  = RISK_COLORS.get(risk, "#FFD600")

            with st.expander(f"{icon}  {txn_id}  —  {risk}  (Score: {score:.0f}/100)"):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown("**🚩 Fraud Reasons**")
                    reasons = result.get("fraud_reasons", [])
                    if reasons:
                        for r in reasons:
                            cls = "danger-box" if risk == "High Risk" else "warn-box"
                            st.markdown(f'<div class="{cls}">🔴 {r}</div>',
                                        unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="info-box">🟢 No fraud indicators — transaction is safe.</div>',
                                    unsafe_allow_html=True)

                with col_b:
                    st.markdown("**🤖 Agent Trace**")
                    for step in result.get("agent_trace", []):
                        agent = step.get("agent", "?")
                        info  = (step.get("result") or step.get("analysis_snippet") or
                                 step.get("risk_score") or step.get("final_decision") or "")
                        st.markdown(f'<div class="info-box">→ <b>{agent}</b>: {info}</div>',
                                    unsafe_allow_html=True)

                if result.get("explanation"):
                    st.markdown("**💡 Explanation**")
                    st.markdown(result["explanation"])

                if result.get("correlation_id"):
                    st.caption(f"🔗 Correlation ID: `{result['correlation_id']}`")


# ══════════════════════════════════════════════════════════════════
# TAB 2 — SINGLE TRANSACTION ANALYSIS
# ══════════════════════════════════════════════════════════════════
with tab_single:
    st.markdown('<div class="section-title">🔎 Analyze a Single Transaction</div>',
                unsafe_allow_html=True)
    st.markdown("Enter transaction details below and click **Analyze** to get an instant fraud assessment.")

    with st.form("single_txn_form"):
        st.markdown("**Transaction Details**")
        r1c1, r1c2, r1c3 = st.columns(3)
        txn_id  = r1c1.text_input("Transaction ID", value="TXN_CUSTOM_001",
                                   placeholder="e.g. TXN001")
        cust_id = r1c2.text_input("Customer ID", value="CUST_TEST",
                                   placeholder="e.g. CUST_A")
        amount  = r1c3.number_input("Amount (₹)", min_value=0.0, value=5000.0,
                                    step=500.0, format="%.2f")

        r2c1, r2c2, r2c3 = st.columns(3)
        location = r2c1.text_input("Location", value="Mumbai, India",
                                    placeholder="City, Country")
        txn_type = r2c2.selectbox(
            "Transaction Type",
            ["purchase", "withdrawal", "transfer", "deposit", "payment", "refund"],
        )
        txn_time = r2c3.text_input("Time", value="2024-06-15T10:00:00",
                                    placeholder="YYYY-MM-DDTHH:MM:SS")

        st.markdown("---")
        col_btn2, col_hint = st.columns([1, 4])
        analyze_btn = col_btn2.form_submit_button("🔍 Analyze Transaction", type="primary")
        col_hint.markdown(
            "_Try: Amount=`200000`, Location=`Lagos, Nigeria`, Type=`transfer` for High Risk_"
        )

    if analyze_btn:
        custom_txn = {
            "transaction_id":   txn_id,
            "customer_id":      cust_id,
            "amount":           amount,
            "location":         location,
            "transaction_type": txn_type,
            "time":             txn_time,
        }

        with st.spinner("🧠 Running multi-agent fraud analysis…"):
            if use_ai and api_ok:
                try:
                    orchestrator = FraudDetectionOrchestrator()
                    result = orchestrator.analyze(custom_txn, SAMPLE_TRANSACTIONS)
                except Exception as e:
                    st.warning(f"AI failed: {e} — using rule-based fallback.")
                    result = _rules_only_result(custom_txn, FraudDetectionRules())
            else:
                result = _rules_only_result(custom_txn, FraudDetectionRules())

        risk  = result.get("risk_level", "Suspicious")
        icon  = RISK_ICONS.get(risk, "⚠️")
        score = result.get("risk_score", 0)
        color = RISK_COLORS.get(risk, "#FFD600")

        # Verdict banner
        st.markdown(_verdict_html(risk, icon, score), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Three KPI cards ───────────────────────────────────────
        k1, k2, k3 = st.columns(3)
        cls = RISK_CLASS.get(risk, "total")
        k1.markdown(_metric_card("Risk Level", f"{icon} {risk}", cls), unsafe_allow_html=True)
        k2.markdown(_metric_card("Risk Score", f"{score:.0f} / 100", cls), unsafe_allow_html=True)
        action_map = {"none": "✅ Allow", "alert_customer": "📧 Alert Customer",
                      "block_transaction": "🚫 Block", "monitor": "👁️ Monitor"}
        action_label = action_map.get(result.get("recommended_action", "monitor"), "Monitor")
        k3.markdown(_metric_card("Action", action_label, cls), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Fraud reasons + Agent trace ───────────────────────────
        col_reasons, col_trace = st.columns(2)

        with col_reasons:
            st.markdown("**🚩 Fraud Reasons**")
            reasons = result.get("fraud_reasons", [])
            if reasons:
                for r in reasons:
                    box_cls = "danger-box" if risk == "High Risk" else "warn-box"
                    st.markdown(f'<div class="{box_cls}">🔴 {r}</div>',
                                unsafe_allow_html=True)
            else:
                st.markdown('<div class="info-box">🟢 No fraud indicators. Transaction passed all checks.</div>',
                            unsafe_allow_html=True)

        with col_trace:
            st.markdown("**🤖 Agent Trace**")
            for step in result.get("agent_trace", []):
                agent = step.get("agent", "?")
                info  = (step.get("result") or step.get("final_decision") or
                         str(step.get("risk_score", "")) or "")
                st.markdown(f'<div class="info-box">→ <b>{agent}</b>: {info}</div>',
                            unsafe_allow_html=True)

        # ── Gauge + Explanation ───────────────────────────────────
        st.markdown("---")
        gauge_col, expl_col = st.columns([1, 2])

        with gauge_col:
            st.markdown("**📊 Risk Gauge**")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                number={"font": {"color": color, "size": 36}},
                title={"text": "Fraud Risk Score", "font": {"color": "#c8d8e8", "size": 14}},
                gauge={
                    "axis": {"range": [0, 100],
                              "tickcolor": "#c8d8e8",
                              "tickfont": {"color": "#c8d8e8"}},
                    "bar": {"color": color, "thickness": 0.25},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 40],  "color": "rgba(0,230,118,0.15)"},
                        {"range": [40, 70], "color": "rgba(255,214,0,0.15)"},
                        {"range": [70, 100],"color": "rgba(255,23,68,0.15)"},
                    ],
                    "threshold": {
                        "line": {"color": "#ff1744", "width": 3},
                        "thickness": 0.75,
                        "value": 70,
                    },
                },
            ))
            fig_gauge.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                height=250,
                margin=dict(t=40, b=10, l=20, r=20),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with expl_col:
            if result.get("explanation"):
                st.markdown("**💡 Full Explanation**")
                st.markdown(result["explanation"])

        if result.get("correlation_id"):
            st.caption(f"🔗 Correlation ID: `{result['correlation_id']}`")


# ══════════════════════════════════════════════════════════════════
# TAB 3 — LOAD TESTS
# ══════════════════════════════════════════════════════════════════
with tab_load:
    st.markdown('<div class="section-title">⚡ K6 Load Test Results</div>',
                unsafe_allow_html=True)

    if K6_REPORT.exists():
        try:
            k6_data = json.loads(K6_REPORT.read_text())
            metrics = k6_data.get("metrics", {})
            dur     = metrics.get("http_req_duration", {})

            # ── Latency percentiles bar chart ─────────────────────
            p_vals = {
                "P50 (Median)": dur.get("med", 0),
                "P90":          dur.get("p(90)", dur.get("p90", 0)),
                "P95":          dur.get("p(95)", dur.get("p95", 0)),
                "P99":          dur.get("p(99)", dur.get("p99", 0)),
            }
            fig_lat = px.bar(
                x=list(p_vals.keys()), y=list(p_vals.values()),
                labels={"x": "Percentile", "y": "Latency (ms)"},
                title="Response Latency Percentiles",
                color=list(p_vals.values()),
                color_continuous_scale=["#00e676", "#ffd600", "#ff1744"],
            )
            fig_lat.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,27,42,0.6)",
                font_color="#c8d8e8",
                coloraxis_showscale=False,
                margin=dict(t=40, b=10, l=10, r=10),
            )

            # ── Error rate gauge ──────────────────────────────────
            error_rate = metrics.get("http_req_failed", {}).get("rate", 0)
            fig_err = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(error_rate * 100, 2),
                number={"suffix": "%", "font": {"color": "#c8d8e8"}},
                title={"text": "Error Rate", "font": {"color": "#c8d8e8", "size": 14}},
                gauge={
                    "axis": {"range": [0, 20], "tickcolor": "#c8d8e8",
                             "tickfont": {"color": "#c8d8e8"}},
                    "bar": {"color": "#448aff"},
                    "bgcolor": "rgba(0,0,0,0)",
                    "steps": [
                        {"range": [0, 5],  "color": "rgba(0,230,118,0.2)"},
                        {"range": [5, 10], "color": "rgba(255,214,0,0.2)"},
                        {"range": [10, 20],"color": "rgba(255,23,68,0.2)"},
                    ],
                    "threshold": {"line": {"color": "#ff1744", "width": 3},
                                  "thickness": 0.75, "value": 5},
                },
            ))
            fig_err.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                height=220,
                margin=dict(t=40, b=10, l=20, r=20),
            )

            rps       = metrics.get("http_reqs", {}).get("rate", 0)
            total_req = int(metrics.get("http_reqs", {}).get("count", 0))
            avg_ms    = round(dur.get("avg", 0), 1)

            # Metric cards row
            st.markdown("<br>", unsafe_allow_html=True)
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.markdown(_metric_card("Total Requests", f"{total_req:,}", "total"),
                         unsafe_allow_html=True)
            mc2.markdown(_metric_card("Req / sec", f"{rps:.1f}", "total"),
                         unsafe_allow_html=True)
            mc3.markdown(_metric_card("Avg Latency", f"{avg_ms} ms", "total"),
                         unsafe_allow_html=True)
            mc4.markdown(_metric_card("Error Rate", f"{error_rate*100:.2f}%",
                         "high" if error_rate > 0.05 else "safe"),
                         unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            lc, rc = st.columns(2)
            with lc:
                st.plotly_chart(fig_lat, use_container_width=True)
            with rc:
                st.plotly_chart(fig_err, use_container_width=True)

        except Exception as e:
            st.error(f"Failed to parse K6 report: {e}")
    else:
        st.info("No K6 results yet. Start all 3 MCP servers, then run:")
        st.code(
            "k6 run load_tests/k6_script.js "
            "--summary-export=reports/k6_summary.json",
            language="bash",
        )
        st.markdown("Or for a quick smoke test only:")
        st.code(
            "k6 run --vus 1 --duration 30s load_tests/k6_script.js "
            "--summary-export=reports/k6_summary.json",
            language="bash",
        )

    with st.expander("📋 Test Scenarios"):
        st.markdown("""
| Scenario | VUs | Duration | Purpose |
|----------|-----|----------|---------|
| Smoke    | 1   | 30s      | Baseline check — verify server is responding |
| Load     | 50  | 5 min    | Normal traffic — check P95 latency |
| Stress   | 50→200 | 10 min | Find breaking point |

**Targets:**
- Fraud DB MCP (port 8002): `get_transaction_history`, `get_fraud_blacklist`, `get_fraud_statistics`
- Geo Risk MCP (port 8003): `get_country_risk_score`, `verify_domestic_location`
- Orchestrator MCP (port 8004): `get_system_status` *(not `analyze_transaction` — avoids API cost)*

**Thresholds:** P95 latency < 2000 ms · Error rate < 10%
""")

    with st.expander("📦 Install K6"):
        st.code("""# Debian/Ubuntu
sudo gpg --no-default-keyring \\
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \\
  --keyserver hkp://keyserver.ubuntu.com:80 \\
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \\
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6""", language="bash")


# ══════════════════════════════════════════════════════════════════
# TAB 4 — TRANSACTION GRAPH
# ══════════════════════════════════════════════════════════════════
with tab_graph:
    st.markdown('<div class="section-title">🕸️ Transaction Relationship Graph</div>',
                unsafe_allow_html=True)
    st.markdown(
        "Nodes: **🔵 Customer** · **🟢/🟡/🔴 Transaction** (by risk) · **🟣 Location**  "
        "   Edges: MADE · AT_LOCATION · FOLLOWS (rapid succession)"
    )

    # Build graph — enrich with analysis results if batch has been run
    batch_results = st.session_state.get("batch_results")
    G = build_fraud_graph(SAMPLE_TRANSACTIONS, batch_results)
    stats = get_graph_stats(G)

    if not batch_results:
        st.info("Run **Batch Analysis** (Tab 1) first to see risk colors on transaction nodes.")

    # ── Stats cards ───────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    gs1, gs2, gs3, gs4 = st.columns(4)
    gs1.markdown(_metric_card("Total Nodes", stats["total_nodes"], "total"),
                 unsafe_allow_html=True)
    gs2.markdown(_metric_card("Total Edges", stats["total_edges"], "total"),
                 unsafe_allow_html=True)
    gs3.markdown(_metric_card("High-Risk Txns", stats["high_risk_transactions"], "high"),
                 unsafe_allow_html=True)
    gs4.markdown(_metric_card("Fraud Clusters", stats["fraud_clusters"], "susp"),
                 unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filter controls ───────────────────────────────────────────
    f1, f2, _ = st.columns([1, 1, 2])
    risk_filter = f1.selectbox(
        "Filter by Risk Level", ["All", "High Risk", "Suspicious", "Safe", "Unknown"],
        key="graph_risk_filter",
    )
    all_customers = sorted({
        d["customer_id"]
        for _, d in G.nodes(data=True)
        if d.get("type") == "customer"
    })
    cust_filter = f2.selectbox(
        "Filter by Customer", ["All"] + all_customers,
        key="graph_cust_filter",
    )

    # Determine which transaction nodes to include based on filters
    include_txn_nodes: set = set()
    for node_id, data in G.nodes(data=True):
        if data.get("type") != "transaction":
            continue
        rl = data.get("risk_level") or "Unknown"
        cust = data.get("customer_id", "")
        if risk_filter != "All" and rl != risk_filter:
            continue
        if cust_filter != "All" and cust != cust_filter:
            continue
        include_txn_nodes.add(node_id)

    # Build the subgraph: include matching transactions + their connected nodes
    include_nodes: set = set(include_txn_nodes)
    for node_id in include_txn_nodes:
        for neighbor in list(G.predecessors(node_id)) + list(G.successors(node_id)):
            include_nodes.add(neighbor)

    subG = G.subgraph(include_nodes) if include_nodes else G

    # ── pyvis interactive graph ───────────────────────────────────
    try:
        from pyvis.network import Network

        COLOR_MAP = {
            ("transaction", "High Risk"):    "#ff1744",
            ("transaction", "Suspicious"):   "#ffd600",
            ("transaction", "Safe"):         "#00e676",
            ("transaction", None):           "#448aff",
            ("customer",    None):           "#29b6f6",
            ("location",    None):           "#ce93d8",
        }

        net = Network(
            height="580px", width="100%",
            bgcolor="#0d1b2a", font_color="#c8d8e8",
            directed=True,
        )
        net.set_options("""
        {
          "physics": {
            "stabilization": {"iterations": 150},
            "barnesHut": {"gravitationalConstant": -8000, "springLength": 120}
          },
          "edges": {"arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
                    "color": {"color": "#4a6080", "highlight": "#ffffff"},
                    "font": {"color": "#8899aa", "size": 10}},
          "nodes": {"font": {"size": 12}}
        }
        """)

        for node_id, data in subG.nodes(data=True):
            ntype = data.get("type", "unknown")
            rl    = data.get("risk_level")
            color = COLOR_MAP.get((ntype, rl), COLOR_MAP.get((ntype, None), "#888888"))
            size  = 20 if ntype == "customer" else (16 if ntype == "transaction" else 12)
            title_parts = [f"<b>{node_id}</b>"]
            if ntype == "transaction":
                title_parts += [
                    f"Amount: ₹{data.get('amount', 0):,.0f}",
                    f"Risk: {rl or 'Unknown'}",
                    f"Score: {data.get('risk_score') or '—'}",
                ]
            elif ntype == "location":
                title_parts += [
                    f"Risk score: {data.get('risk_score', '—')}",
                    f"Domestic: {data.get('is_domestic', False)}",
                ]
            net.add_node(
                node_id,
                label=data.get("label", node_id),
                color=color,
                size=size,
                title="<br>".join(title_parts),
            )

        for src, dst, edata in subG.edges(data=True):
            etype = edata.get("type", "")
            width = 2 if etype == "FOLLOWS" else 1
            net.add_edge(src, dst, label=etype, width=width)

        html_str = net.generate_html()
        components.html(html_str, height=600, scrolling=False)

    except ImportError:
        st.warning(
            "pyvis is not installed. Run `pip install pyvis` then restart the app."
        )
        # Fallback: static table of nodes
        node_rows = [
            {"Node": nid, "Type": d.get("type"), "Risk": d.get("risk_level") or "—",
             "Label": d.get("label", nid)}
            for nid, d in subG.nodes(data=True)
        ]
        st.dataframe(pd.DataFrame(node_rows), use_container_width=True)

    st.markdown("---")

    # ── Graph statistics ──────────────────────────────────────────
    with st.expander("📊 Graph Statistics"):
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.markdown(f"""
| Metric | Value |
|--------|-------|
| Customer nodes | {stats['customer_nodes']} |
| Transaction nodes | {stats['transaction_nodes']} |
| Location nodes | {stats['location_nodes']} |
| High-risk transactions | {stats['high_risk_transactions']} |
| Fraud clusters | {stats['fraud_clusters']} |
""")
        with col_stat2:
            st.markdown("**Top 5 nodes by degree centrality:**")
            for entry in stats["top5_by_centrality"]:
                st.markdown(f"- `{entry['node']}` → {entry['centrality']:.4f}")

    # ── Neo4j Cypher export ───────────────────────────────────────
    with st.expander("🗄️ Export to Neo4j Cypher"):
        st.markdown("Copy-paste into Neo4j Browser or `cypher-shell` to import the graph.")
        cypher = to_cypher_export(G)
        st.code(cypher, language="cypher")


# ══════════════════════════════════════════════════════════════════
# TAB 5 — ABOUT
# ══════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown('<div class="section-title">About This System</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("""
### 🧠 Multi-Agent Architecture

| Agent | Model | Role |
|-------|-------|------|
| RulesAgent | Python (no LLM) | Applies 4 deterministic rules |
| PatternAgent | claude-sonnet-4-6 | Behavioral pattern analysis |
| RiskScorerAgent | claude-opus-4-8 + thinking | Deep risk scoring |
| CoordinatorAgent | claude-opus-4-8 | Synthesizes final decision |

### 🔧 Four Fraud Rules

| Rule | Trigger | Weight |
|------|---------|--------|
| 💸 High Amount | ≥ ₹1,00,000 | 35 pts |
| 📍 Unusual Location | Fraud hotspot / unknown | 30 pts |
| ⚡ Rapid Succession | 3+ txns in 5 minutes | 25 pts |
| 🌍 International | Outside India | 15 pts |

**0 rules → Safe &nbsp;·&nbsp; 1 rule → Suspicious &nbsp;·&nbsp; 2+ rules → High Risk**
""")

    with col_right:
        st.markdown("""
### 🔄 Request Flow

```
User Request
    ↓
FraudHookManager.pre_process()
  • Validate inputs
  • Rate limit check
  • Generate correlation ID
    ↓
FraudDetectionOrchestrator
  → RulesAgent       (instant)
  → PatternAgent     (Sonnet)
  → RiskScorerAgent  (Opus + thinking)
  → CoordinatorAgent (Opus)
    ↓
FraudHookManager.post_process()
  • Compliance check
  • Fairness flag
  • Audit log (audit.jsonl)
  • Emit metrics
    ↓
Result: Safe / Suspicious / High Risk
```

### 🔌 MCP Servers (Multi-MCP Bonus)

| Server | Port | Tools |
|--------|------|-------|
| Fraud DB | 8002 | Transaction history, blacklist |
| Geo Risk | 8003 | Country risk, IP lookup |

### 🛡️ Governance
- Input validation on every request
- Rate limiting: 20 requests/minute
- Bias/fairness checks on High Risk decisions
- Append-only `audit.jsonl` log
- Self-healing: retry × 3 → model fallback
""")

    st.markdown("---")
    st.markdown(
        "**Tech Stack:** Python 3.14 · Anthropic SDK (claude-opus-4-8) · "
        "Streamlit · Plotly · FastMCP · Pandas · Pytest"
    )
