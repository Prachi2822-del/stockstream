"""
dashboard/app.py
StockStream AI Investment Platform
Full dashboard with live charts + AI advisor chat sidebar.

Run with: streamlit run dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import boto3
import time
from decimal import Decimal
from datetime import datetime, timezone
from dotenv import load_dotenv

from analyser.technical import analyse_stock, compare_all_stocks
from ai.advisor import ask_advisor

load_dotenv()

# Page config 

st.set_page_config(
    page_title="StockStream AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS 

st.markdown("""
<style>
    .main { padding: 0rem 1rem; }
    .stock-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
        border: 1px solid #2d3250;
    }
    .signal-buy        { color: #00d4aa; font-weight: bold; font-size: 13px; }
    .signal-sell       { color: #ff4b6e; font-weight: bold; font-size: 13px; }
    .signal-hold       { color: #ffd700; font-weight: bold; font-size: 13px; }
    .signal-strong-buy { color: #00ff88; font-weight: bold; font-size: 14px; }
    .price-up          { color: #00d4aa; }
    .price-down        { color: #ff4b6e; }
    .disclaimer {
        background: #2a1a1a;
        border: 1px solid #ff4b6e;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 12px;
        color: #ff9999;
        margin-bottom: 10px;
    }
    .chat-msg-user {
        background: #2d3250;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 13px;
        color: #ffffff;
    }
    .chat-msg-ai {
        background: #1e2130;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 13px;
        color: #ffffff;
        border-left: 3px solid #a78bfa;
    }
</style>
""", unsafe_allow_html=True)

STOCKS = ["AAPL", "GOOGLE", "MSFT", "AMZN", "TSLA"]

# AWS connection

@st.cache_resource
def get_dynamodb():
    return boto3.resource(
        "dynamodb",
        region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
    )

dynamodb = get_dynamodb()
table    = dynamodb.Table(os.getenv("DYNAMODB_TABLE", "stock_prices"))


# Data fetching 

def fetch_latest_price(symbol: str) -> dict:
    """Get the most recent price using query — fast and accurate."""
    try:
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("symbol").eq(symbol),
            ScanIndexForward=False,
            Limit=1
        )
        items = result.get("Items", [])
        if items:
            item = items[0]
            return {
                "symbol":     symbol,
                "price":      float(item["price"]),
                "pct_change": float(item.get("pct_change", 0)),
                "volume":     int(item.get("volume", 0)),
                "timestamp":  str(item["timestamp"]),
                "source":     str(item.get("source", "simulator"))
            }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return {"symbol": symbol, "price": 0, "pct_change": 0,
            "volume": 0, "source": "unknown"}


def fetch_price_history(symbol: str, limit: int = 100) -> pd.DataFrame:
    """Get price history using query — returns all records for a symbol."""
    try:
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("symbol").eq(symbol),
            ScanIndexForward=True,
            Limit=limit
        )
        items = result.get("Items", [])
        if not items:
            return pd.DataFrame()

        df = pd.DataFrame(items)
        df["price"]      = df["price"].astype(float)
        df["volume"]     = df["volume"].astype(int)
        df["pct_change"] = df["pct_change"].astype(float)
        df["timestamp"]  = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp").reset_index(drop=True)

    except Exception as e:
        print(f"Error fetching history for {symbol}: {e}")
        return pd.DataFrame()

# Chart builders

def build_price_chart(symbol: str, df: pd.DataFrame, analysis: dict) -> go.Figure:
    """Build price chart with MA lines overlaid."""
    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["price"],
        name="Price", line=dict(color="#00d4aa", width=2),
        fill="tozeroy", fillcolor="rgba(0,212,170,0.05)"
    ))

    # Moving averages
    if "MA7" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["MA7"],
            name="MA7", line=dict(color="#ffd700", width=1, dash="dot")
        ))
    if "MA20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["MA20"],
            name="MA20", line=dict(color="#ff9900", width=1, dash="dot")
        ))

    # Signal badge in title
    short_signal = analysis.get("short_term", "N/A")
    rsi          = analysis.get("rsi", 0)

    fig.update_layout(
        title=f"{symbol} — {short_signal} | RSI: {rsi:.1f}",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white"),
        legend=dict(bgcolor="#1e2130"),
        xaxis=dict(gridcolor="#2d3250"),
        yaxis=dict(gridcolor="#2d3250", title="Price (USD)"),
        margin=dict(l=0, r=0, t=40, b=0),
        height=350
    )
    return fig


def build_rsi_chart(df: pd.DataFrame) -> go.Figure:
    """Build RSI chart with overbought/oversold zones."""
    fig = go.Figure()

    if "RSI" not in df.columns:
        return fig

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["RSI"],
        name="RSI", line=dict(color="#a78bfa", width=2)
    ))

    # Overbought zone
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,75,110,0.15)",
                  line_width=0, annotation_text="Overbought")
    # Oversold zone
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,212,170,0.15)",
                  line_width=0, annotation_text="Oversold")
    # Midline
    fig.add_hline(y=50, line_dash="dot", line_color="#555555")

    fig.update_layout(
        title="RSI Indicator",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis=dict(gridcolor="#2d3250"),
        yaxis=dict(gridcolor="#2d3250", range=[0, 100]),
        margin=dict(l=0, r=0, t=40, b=0),
        height=200
    )
    return fig


def build_volume_chart(df: pd.DataFrame) -> go.Figure:
    """Build volume bar chart."""
    fig = go.Figure()

    colors = ["#00d4aa" if p >= 0 else "#ff4b6e"
              for p in df.get("pct_change", [0] * len(df))]

    fig.add_trace(go.Bar(
        x=df["timestamp"], y=df["volume"],
        name="Volume", marker_color=colors
    ))

    fig.update_layout(
        title="Volume",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis=dict(gridcolor="#2d3250"),
        yaxis=dict(gridcolor="#2d3250"),
        margin=dict(l=0, r=0, t=40, b=0),
        height=180
    )
    return fig


# Signal badge 

def signal_badge(signal: str) -> str:
    colors = {
        "STRONG BUY": "🟢🟢",
        "BUY":        "🟢",
        "HOLD":       "🟡",
        "SELL":       "🔴",
        "STRONG SELL":"🔴🔴",
        "NO DATA":    "⚪"
    }
    return f"{colors.get(signal, '⚪')} {signal}"


# Main app

def main():

    # Header
    st.markdown("## 📈 StockStream AI Investment Platform")

    # Top price cards
    cols = st.columns(5)
    for i, symbol in enumerate(STOCKS):
        data = fetch_latest_price(symbol)
        pct  = data["pct_change"]
        arrow= "▲" if pct >= 0 else "▼"
        color= "price-up" if pct >= 0 else "price-down"
        with cols[i]:
            source_badge = "🟢 LIVE" if data.get('source') == 'yahoo_finance' else "🔵 SIM"
            st.markdown(f"""
            <div class="stock-card">
                <div style="font-size:14px;font-weight:600;color:white">{symbol}</div>
                <div style="font-size:20px;font-weight:700;color:white">
                    ${data['price']:.2f}
                </div>
                <div class="{color}">
                    {arrow} {abs(pct):.2f}%
                </div>
                <div style="font-size:10px;color:#888;margin-top:4px">
                    {source_badge}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Main layout: charts left, chat right 
    chart_col, chat_col = st.columns([3, 2])

    # LEFT: Charts
    with chart_col:
        selected = st.selectbox(
            "Select stock to analyse",
            STOCKS,
            key="stock_selector"
        )

        # Fetch data and run analysis
        df       = fetch_price_history(selected, limit=100)
        analysis = analyse_stock(selected)

        if not df.empty:
            from analyser.technical import (
                calculate_moving_averages,
                calculate_rsi,
                calculate_macd,
                calculate_bollinger_bands
            )
            df = calculate_moving_averages(df)
            df = calculate_rsi(df)
            df = calculate_macd(df)
            df = calculate_bollinger_bands(df)

            # Price + MA chart
            st.plotly_chart(
                build_price_chart(selected, df, analysis),
                use_container_width='stretch'
            )

            # RSI + Volume side by side
            r_col, v_col = st.columns(2)
            with r_col:
                st.plotly_chart(
                    build_rsi_chart(df),
                    use_container_width='stretch'
                )
            with v_col:
                st.plotly_chart(
                    build_volume_chart(df),
                    use_container_width='stretch'
                )

            # Signal summary
            st.markdown("### Signal Summary")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Short Term",  signal_badge(analysis.get("short_term","N/A")))
            s2.metric("Long Term",   signal_badge(analysis.get("long_term","N/A")))
            s3.metric("RSI",         f"{analysis.get('rsi', 0):.1f}")
            s4.metric("Confidence",  f"{analysis.get('confidence', 0)}%")

            # Reasons
            if analysis.get("reasons"):
                with st.expander("Why this signal?"):
                    for reason in analysis["reasons"]:
                        st.write(f"→ {reason}")
        else:
            st.warning(f"No data for {selected} — run the producer first")

    # RIGHT: AI Chat
    with chat_col:
        st.markdown("### 🤖 AI Investment Advisor")

        # Quick question buttons
        st.markdown("**Quick questions:**")
        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("Best buy\nnow?", use_container_width='stretch'):
                st.session_state.pending_question = \
                    "Which stock is the best to buy right now for short term?"
        with q2:
            if st.button("Best long\nterm?", use_container_width='stretch'):
                st.session_state.pending_question = \
                    "Which stock is best for long term investment of 6 months?"
        with q3:
            if st.button("Market\noverview?", use_container_width='stretch'):
                st.session_state.pending_question = \
                    "Give me a full market overview of all 5 stocks"

        # Stock-specific quick buttons
        qa, qb = st.columns(2)
        with qa:
            if st.button(f"Analyse {selected}", use_container_width='stretch'):
                st.session_state.pending_question = \
                    f"Give me a full analysis of {selected} — should I buy or sell?"
        with qb:
            if st.button("Riskiest\nstock?", use_container_width='stretch'):
                st.session_state.pending_question = \
                    "Which of the 5 stocks is the riskiest right now and why?"

        # Chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Chat container
        chat_container = st.container(height=380)
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div class="chat-msg-user">
                    👤 {msg['content']}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-msg-ai">
                    🤖 {msg['content']}
                    </div>
                    """, unsafe_allow_html=True)

        # Process pending question from buttons
        if "pending_question" in st.session_state and st.session_state.pending_question:
            question = st.session_state.pending_question
            st.session_state.pending_question = ""
            st.session_state.chat_history.append({
                "role": "user", "content": question
            })
            with st.spinner("AI advisor thinking..."):
                answer = ask_advisor(question)
            st.session_state.chat_history.append({
                "role": "assistant", "content": answer
            })
            st.rerun()

        # Chat input
        user_input = st.chat_input("Ask anything about stocks...")
        if user_input:
            st.session_state.chat_history.append({
                "role": "user", "content": user_input
            })
            with st.spinner("AI advisor thinking..."):
                answer = ask_advisor(user_input)
            st.session_state.chat_history.append({
                "role": "assistant", "content": answer
            })
            st.rerun()

        # Clear chat button
        if st.button("Clear chat", use_container_width='stretch'):
            st.session_state.chat_history = []
            st.rerun()

    # Auto refresh every 30 seconds
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} · "
               f"Auto-refreshes every 30 seconds")

    if st.button("🔄 Refresh prices"):
        st.rerun()

if __name__ == "__main__":
    main()