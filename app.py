import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# ==========================================
# 1. 系統核心設定
# ==========================================
APP_NAME = "超級績效 智能趨勢選股系統"
VERSION = "V26"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"📈 {APP_NAME} {VERSION}")

# 初始化持久化記憶
if 'scan_df' not in st.session_state:
    st.session_state.scan_df = None
if 'active_tickers' not in st.session_state:
    st.session_state.active_tickers = []

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.session_state.scan_df = None
    st.session_state.active_tickers = []
    st.rerun()

# ==========================================
# 2. 數據抓取引擎
# ==========================================

@st.cache_data(ttl=86400)
def fetch_full_sp500_data():
    """抓取標普500名單，並確保 11 大板塊完整性"""
    fallback_sectors = [
        "Information Technology", "Health Care", "Financials", "Consumer Discretionary", 
        "Communication Services", "Industrials", "Consumer Staples", "Energy", 
        "Utilities", "Real Estate", "Materials"
    ]
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        res = requests.get(url, headers=headers, timeout=10)
        df = pd.read_html(res.text)[0]
        df['Symbol'] = df['Symbol'].str.replace('.', '-', regex=False)
        return df[['Symbol', 'GICS Sector']], sorted(df['GICS Sector'].unique().tolist())
    except:
        # 若連線失敗，返回基本清單與硬編碼的 11 大板塊名單
        st.sidebar.warning("⚠️ 維基百科連線受限，已加載預設板塊清單。")
        dummy_df = pd.DataFrame([{"Symbol": "AAPL", "GICS Sector": "Information Technology"}])
        return dummy_df, fallback_sectors

@st.cache_data(ttl=3600)
def get_spy_bench():
    try:
        spy = yf.Ticker("SPY").history(period="1y")
        return (spy['Close'].iloc[-1] / spy['Close'].iloc[-126]) - 1 if len(spy) > 126 else 0.05
    except: return 0.05

SPY_6M = get_spy_bench()

@st.cache_data(ttl=3600)
def get_sepa_data(ticker):
    try:
        s = yf.Ticker(ticker)
        df = s.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return None, None
        
        # 技術指標
        df['50MA'] = df['Close'].rolling(50).mean()
        df['150MA'] = df['Close'].rolling(150).mean()
        df['200MA'] = df['Close'].rolling(200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(50).mean()
        
        # 財報提取
        info = s.info
        fund = {
            "eps": (info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth') or 0) * 100,
            "rev": (info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth') or 0) * 100
        }
        return df, fund
    except: return None, None

# ==========================================
# 3. 掃描器頁面
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 批量趨勢篩選雷達 (11大板塊解鎖版)")
    
    # 獲取板塊數據與名單
    sp_data, all_sectors = fetch_full_sp500_data()

    c1, c2 = st.columns(2)
    with c1:
        mode = st.radio("掃描範圍：", ["🔥 熱門精選 (22檔)", "🇺🇸 標普 500 全掃", "📂 標普 500 分板塊"])
        target_sector = st.selectbox("選擇要掃描的板塊：", all_sectors) if "分板塊" in mode else None
    with c2:
        sort_key = st.selectbox("結果排序依據：", ["綜合潛力", "RS強度", "EPS成長", "營收成長"])
        min_s = st.slider("Minervini 分數門檻：", 4, 7, 7)
        only_rs = st.checkbox("👑 跑贏大盤 (RS > 0)", value=True)

    if st.button("🏁 開始超級績效深度掃描", type="primary"):
        if mode == "🔥 熱門精選 (22檔)":
            tickers = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "COHR", "PLTR", "ARM", "AVGO", "NFLX", "SMCI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT", "AMD", "TSM", "SOFI"]
        elif mode == "🇺🇸 標普 500 全掃":
            tickers = sp_data['Symbol'].tolist() if not sp_data.empty else []
        else:
            # 針對特定板塊過濾
            tickers = sp_data[sp_data['GICS Sector'] == target_sector]['Symbol'].tolist() if not sp_data.empty else []

        if not tickers:
            st.error("❌ 無法取得該範圍的名單，請確認網路連線或嘗試『熱門精選』。")
        else:
            results = []
            bar = st.progress(0)
            status = st.empty()

            for i, t in enumerate(tickers):
                status.text(f"分析中 ({i+1}/{len(tickers)}): {t}")
                df, fund = get_sepa_data(t)
                if df is not None:
                    cur = float(df['Close'].iloc[-1])
                    last = df.iloc[-1]
                    h52, l52 = float(df.tail(252)['High'].max()), float(df.tail(252)['Low'].min())
                    
                    conds = [
                        cur > last['150MA'] and cur > last['200MA'], last['150MA'] > last['200MA'],
                        last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False,
                        last['50MA'] > last['150MA'] and last['50MA'] > last['200MA'],
                        cur > last['50MA'], cur > l52 * 1.3, cur > h52 * 0.75
                    ]
                    score = sum(conds)
                    rs_val = ((cur / df['Close'].iloc[-126]) - 1 - SPY_6M) * 100 if len(df) > 126 else 0
                    
                    if score >= min_s and (rs_val > 0 if only_rs else True):
                        potential = (score/7 * 40) + (min(max(rs_val, 0), 100)/100 * 40) + (min(max(fund['eps'], 0), 100)/100 * 20)
                        results.append({
                            "代號": t, "得分": score, "RS強度": round(rs_val, 1),
                            "綜合潛力": round(potential, 1), "價格": round(cur, 2),
                            "EPS成長": round(fund['eps'], 1), "營收成長": round(fund['rev'], 1)
                        })
                bar.progress((i + 1) / len(tickers))
            
            if results:
                st.session_state.scan_df = pd.DataFrame(results).sort_values(by=sort_key, ascending=False)
                st.session_state.active_tickers = st.session_state.scan_df['代號'].tolist()
                status.success(f"掃描完成！發現 {len(results)} 檔優質標的。")
            else:
                st.session_state.scan_df = None
                status.warning("當前範圍內無標的符合條件。")

    if st.session_state.scan_df is not None:
        st.write("---")
        st.dataframe(st.session_state.scan_df, use_container_width=True, hide_index=True)

# ==========================================
# 4. 個股深度分析頁面
# ==========================================
else:
    st.sidebar.markdown("---")
    if st.session_state.active_tickers:
        target = st.sidebar.selectbox("🎯 快速查看結果", st.session_state.active_tickers)
    else:
        target = st.sidebar.text_input("🎯 手動輸入", value="NVDA").upper()
    
    df, fund = get_sepa_data(target)
    if df is not None:
        st.subheader(f"📊 {target} 趨勢深度分析")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("價格", f"${df['Close'].iloc[-1]:.2f}")
        c2.metric("EPS 成長", f"{fund['eps']:.1f}%")
        c3.metric("RS 強度", f"{((df['Close'].iloc[-1]/df['Close'].iloc[-126])-1-SPY_6M)*100:.1f}%")
        c4.metric("營收 成長", f"{fund['rev']:.1f}%")
        
        tabs = st.tabs(["日K", "周K", "月K"])
        def plot_futu(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            d = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['50MA'], name='50MA', line=dict(color='#2196F3')), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['150MA'], name='150MA', line=dict(color='#FFC107')), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['200MA'], name='200MA', line=dict(color='#F44336')), row=1, col=1)
            cols = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in d.iterrows()]
            fig.add_trace(go.Bar(x=d.index, y=d['Volume'], name='成交量', marker_color=cols), row=2, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['Vol_50MA'], name='均量', line=dict(color='orange')), row=2, col=1)
            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
            return fig
        
        with tabs[0]: st.plotly_chart(plot_futu(df), use_container_width=True)
        with tabs[1]:
            w = yf.Ticker(target).history(period="5y", interval="1wk")
            if not w.empty:
                for ma in [50, 150, 200]: w[f'{ma}MA'] = w['Close'].rolling(ma).mean()
                w['Vol_50MA'] = w['Volume'].rolling(50).mean()
                st.plotly_chart(plot_futu(w), use_container_width=True)
        with tabs[2]:
            m_data = yf.Ticker(target).history(period="max", interval="1mo")
            if not m_data.empty:
                for ma in [50, 150, 200]: m_data[f'{ma}MA'] = m_data['Close'].rolling(ma).mean()
                m_data['Vol_50MA'] = m_data['Volume'].rolling(50).mean()
                st.plotly_chart(plot_futu(m_data), use_container_width=True)
