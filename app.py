import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# ==========================================
# 1. 系統設定與初始化
# ==========================================
APP_NAME = "超級績效 智能趨勢選股系統"
VERSION = "V23"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"📈 {APP_NAME} {VERSION}")

# 初始化 Session State (跨頁面記憶)
if 'scan_results_df' not in st.session_state:
    st.session_state.scan_results_df = None
if 'ticker_list' not in st.session_state:
    st.session_state.ticker_list = []

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

if st.sidebar.button("♻️ 強制清空緩存與結果"):
    st.cache_data.clear()
    st.session_state.scan_results_df = None
    st.session_state.ticker_list = []
    st.rerun()

# ==========================================
# 2. 核心數據引擎
# ==========================================

@st.cache_data(ttl=86400)
def fetch_sp500_with_sectors():
    """從 Wikipedia 抓取標普 500 代號與板塊資訊"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url, headers=headers)
        df = pd.read_html(response.text)[0]
        # 轉換代號格式 (BRK.B -> BRK-B)
        df['Symbol'] = df['Symbol'].str.replace('.', '-', regex=False)
        return df[['Symbol', 'GICS Sector']]
    except:
        return pd.DataFrame(columns=['Symbol', 'GICS Sector'])

@st.cache_data(ttl=3600)
def get_spy_benchmark():
    spy = yf.Ticker("SPY").history(period="1y")
    if not spy.empty and len(spy) > 126:
        return (spy['Close'].iloc[-1] / spy['Close'].iloc[-126]) - 1
    return 0.05

SPY_BENCHMARK = get_spy_benchmark()

@st.cache_data(ttl=3600)
def get_stock_data_v23(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return None, None
        
        # 均線計算
        df['50MA'] = df['Close'].rolling(50).mean()
        df['150MA'] = df['Close'].rolling(150).mean()
        df['200MA'] = df['Close'].rolling(200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(50).mean()
        
        # 財報抓取
        info = {}
        try: info = stock.info
        except: pass
        eps_g = info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth')
        rev_g = info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth')
        
        fund = {"eps": eps_g * 100 if eps_g else 0, "rev": rev_g * 100 if rev_g else 0}
        return df, fund
    except: return None, None

def evaluate_v23(df, fund):
    cur = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    h52, l52 = float(df.tail(252)['High'].max()), float(df.tail(252)['Low'].min())
    
    conds = [
        cur > last['150MA'] and cur > last['200MA'],
        last['150MA'] > last['200MA'],
        last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False,
        last['50MA'] > last['150MA'] and last['50MA'] > last['200MA'],
        cur > last['50MA'],
        cur > l52 * 1.3,
        cur > h52 * 0.75
    ]
    
    ret_6m = (cur / df['Close'].iloc[-126]) - 1 if len(df) > 126 else 0
    rs_val = (ret_6m - SPY_BENCHMARK) * 100
    
    return sum(conds), {"price": cur, "rs": rs_val, "eps": fund['eps'], "rev": fund['rev']}

# ==========================================
# 3. 模式一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 批量趨勢篩選雷達 (美股全板塊支援)")
    
    # 預加載板塊數據
    sp500_data = fetch_sp500_with_sectors()
    sectors = sorted(sp500_data['GICS Sector'].unique().tolist()) if not sp500_data.empty else []

    col_a, col_b = st.columns([1, 1])
    with col_a:
        pool_mode = st.radio("掃描範圍：", ["🔥 熱門精選 (22檔)", "🇺🇸 標普 500 全板塊掃描", "📂 標普 500 分板塊掃描"])
        if pool_mode == "📂 標普 500 分板塊掃描":
            selected_sector = st.selectbox("請選擇板塊：", sectors)
    with col_b:
        min_score = st.slider("Minervini 分數門檻：", 4, 7, 7)
        filter_rs = st.checkbox("👑 僅顯示跑贏大盤 (RS > 0)", value=True)

    if st.button("🏁 開始超級績效深度掃描", type="primary"):
        if pool_mode == "🔥 熱門精選 (22檔)":
            tickers = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX", 
                       "COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]
        elif pool_mode == "🇺🇸 標普 500 全板塊掃描":
            tickers = sp500_data['Symbol'].tolist()
        else:
            tickers = sp500_data[sp500_data['GICS Sector'] == selected_sector]['Symbol'].tolist()

        temp_results = []
        bar = st.progress(0)
        status = st.empty()

        for i, t in enumerate(tickers):
            status.text(f"分析中 ({i+1}/{len(tickers)}): {t}")
            df, fund = get_stock_data_v23(t)
            if df is not None:
                score, m = evaluate_v23(df, fund)
                rs_ok = m['rs'] > 0 if filter_rs else True
                
                if score >= min_score and rs_ok:
                    temp_results.append({
                        "代號": t, "得分": score, 
                        "RS 強度 (%)": round(m['rs'], 1),
                        "價格": round(m['price'], 2), 
                        "EPS 成長 (%)": round(m['eps'], 1), 
                        "營收 成長 (%)": round(m['rev'], 1)
                    })
            bar.progress((i + 1) / len(tickers))
        
        st.session_state.scan_results_df = pd.DataFrame(temp_results)
        st.session_state.ticker_list = [r['代號'] for r in temp_results]
        status.success(f"掃描完成！找到 {len(temp_results)} 檔符合標的。")

    # 持久化顯示
    if st.session_state.scan_results_df is not None:
        st.write("---")
        st.write("### 📊 掃描結果 (點擊表頭可按 RS 或 EPS 排序)")
        st.dataframe(
            st.session_state.scan_results_df.sort_values(by="RS 強度 (%)", ascending=False),
            use_container_width=True, hide_index=True
        )

# ==========================================
# 4. 模式二：📊 個股深度分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    if st.session_state.ticker_list:
        ticker = st.sidebar.selectbox("🎯 快速查看掃描結果", st.session_state.ticker_list)
    else:
        ticker = st.sidebar.text_input("🎯 手動輸入代號", value="NVDA").upper()
    
    df, fund = get_stock_data_v23(ticker)
    if df is not None:
        score, m = evaluate_v23(df, fund)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("價格", f"${m['price']:.2f}")
        c2.metric("RS 強度", f"{m['rs']:.1f}%")
        c3.metric("EPS 成長", f"{m['eps']:.1f}%")
        c4.metric("門檻得分", f"{score}/7")
        
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
                for ma in [50, 150, 200]: w[f'{ma}MA'] = w['Close'].rolling(ma).mean()
                w['Vol_50MA'] = w['Volume'].rolling(50).mean()
                st.plotly_chart(draw(w), use_container_width=True)
        with tabs[2]:
            m_data = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not m_data.empty:
                for ma in [50, 150, 200]: m_data[f'{ma}MA'] = m_data['Close'].rolling(ma).mean()
                m_data['Vol_50MA'] = m_data['Volume'].rolling(50).mean()
                st.plotly_chart(draw(m_data), use_container_width=True)
