import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# ==========================================
# 1. 系統設定與品牌命名
# ==========================================
APP_NAME = "鷹眼 (EagleEye) 智能趨勢選股系統"
VERSION = "V20"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION}")

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

# 強制重整功能
if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.rerun()

# 預設觀察池
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# ==========================================
# 2. 核心數據引擎
# ==========================================

@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return TECH_GIANTS + GROWTH_STARS

@st.cache_data(ttl=3600)
def load_spy_ref():
    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1d")
        if not spy.empty and len(spy) > 126:
            return (spy['Close'].iloc[-1] / spy['Close'].iloc[-126]) - 1
    except: pass
    return 0.05 

SPY_REF = load_spy_ref()

@st.cache_data(ttl=3600)
def get_stock_data_v20(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return pd.DataFrame(), {}
        
        info = {}
        try:
            info = stock.info # 此處在批量掃描時最容易卡住
        except: pass
        
        # 技術指標
        df['50MA'] = df['Close'].rolling(window=50).mean()
        df['150MA'] = df['Close'].rolling(window=150).mean()
        df['200MA'] = df['Close'].rolling(window=200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
        
        # 財報提取
        eps_g = info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth')
        rev_g = info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth')
        
        return df, {
            "eps": eps_g * 100 if eps_g else None,
            "rev": rev_g * 100 if rev_g else None
        }
    except:
        return pd.DataFrame(), {}

def evaluate_v20(df, fund):
    if df.empty or len(df) < 200: return 0, False, {}
    cur = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    h52, l52 = float(df.tail(252)['High'].max()), float(df.tail(252)['Low'].min())
    
    # 7大準則
    c1 = cur > last['150MA'] and cur > last['200MA']
    c2 = last['150MA'] > last['200MA']
    c3 = last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False
    c4 = last['50MA'] > last['150MA'] and last['50MA'] > last['200MA']
    c5 = cur > last['50MA']
    c6 = cur > l52 * 1.3
    c7 = cur > h52 * 0.75
    score = sum([c1, c2, c3, c4, c5, c6, c7])
    
    ret_6m = (cur / df['Close'].iloc[-126]) - 1 if len(df) > 126 else 0
    vcp = last['Volume'] < (last['Vol_50MA'] * 0.75) if pd.notna(last['Vol_50MA']) else False
    
    return score, (score == 7), {
        "price": cur, "hi": h52, "lo": l52,
        "rs": ret_6m > SPY_REF, "vcp": vcp,
        "eps": fund.get('eps'), "rev": fund.get('rev')
    }

# ==========================================
# 3. 掃描器模式 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼全市場掃描雷達")
    
    col_a, col_b = st.columns(2)
    with col_a:
        pool = st.radio("範圍：", ["🔥 熱門精選", "🇺🇸 標普 500 全部", "✍️ 自訂輸入"])
    with col_b:
        min_s = st.slider("最低門檻：", 4, 7, 6)
        f_rs = st.checkbox("👑 跑贏標普 500", value=True)
        f_growth = st.checkbox("📈 財報正成長", value=False) # 修正：這裡的變數名現在與下方對齊

    if st.button("🏁 啟動全方位掃描", type="primary"):
        tickers = (TECH_GIANTS + GROWTH_STARS) if "熱門" in pool else (fetch_sp500_tickers() if "標普" in pool else [])
        if not tickers:
            tickers = [t.strip().upper() for t in st.text_area("自訂輸入", "COHR, NVDA").split(",") if t.strip()]

        results = []
        bar = st.progress(0)
        status = st.empty()

        for i, t in enumerate(tickers):
            status.text(f"分析中 ({i+1}/{len(tickers)}): {t}")
            df, fund = get_stock_data_v20(t)
            if not df.empty:
                score, is_pass, m = evaluate_v20(df, fund)
                
                # 關鍵修正：確保變數名稱正確對應
                rs_ok = m['rs'] if f_rs else True
                growth_ok = ((m['eps'] and m['eps'] > 0) or (m['rev'] and m['rev'] > 0)) if f_growth else True
                
                if score >= min_s and rs_ok and growth_ok:
                    results.append({
                        "代號": t, "得分": f"{score}/7", "狀態": "🔥 符合" if is_pass else "蓄勢",
                        "價格": f"${m['price']:.2f}", "EPS成長": f"{m['eps']:.1f}%" if m['eps'] else "-",
                        "營收成長": f"{m['rev']:.1f}%" if m['rev'] else "-"
                    })
            bar.progress((i + 1) / len(tickers))
        
        status.success(f"完成！找到 {len(results)} 檔個股。")
        if results: st.table(pd.DataFrame(results))

# ==========================================
# 4. 圖表模式 (Chart)
# ==========================================
else:
    ticker = st.sidebar.text_input("🎯 輸入代號", value="NVDA").upper()
    df, fund = get_stock_data_v20(ticker)
    if not df.empty:
        score, is_pass, m = evaluate_v20(df, fund)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("價格", f"${m['price']:.2f}")
        c2.metric("得分", f"{score}/7")
        c3.metric("EPS成長", f"{m['eps']:.1f}%" if m['eps'] else "N/A")
        c4.metric("營收成長", f"{m['rev']:.1f}%" if m['rev'] else "N/A")
        
        st.markdown("---")
        tabs = st.tabs(["日K", "周K", "月K"])
        def draw(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA', line=dict(color='#2196F3')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA', line=dict(color='#FFC107')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA', line=dict(color='#F44336')), row=1, col=1)
            v_c = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=v_c), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='均量', line=dict(color='rgba(255, 165, 0, 0.6)')), row=2, col=1)
            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
            return fig
        with tabs[0]: st.plotly_chart(draw(df), use_container_width=True)
        with tabs[1]:
            w = yf.Ticker(ticker).history(period="5y", interval="1wk")
            if not w.empty:
                w['50MA'], w['150MA'], w['200MA'] = w['Close'].rolling(50).mean(), w['Close'].rolling(150).mean(), w['Close'].rolling(200).mean()
                w['Vol_50MA'] = w['Volume'].rolling(50).mean()
                st.plotly_chart(draw(w), use_container_width=True)
        with tabs[2]:
            m_data = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not m_data.empty:
                m_data['50MA'], m_data['150MA'], m_data['200MA'] = m_data['Close'].rolling(50).mean(), m_data['Close'].rolling(150).mean(), m_data['Close'].rolling(200).mean()
                m_data['Vol_50MA'] = m_data['Volume'].rolling(50).mean()
                st.plotly_chart(draw(m_data), use_container_width=True)
