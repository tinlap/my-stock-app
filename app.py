import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# ==========================================
# 1. 系統核心設定與專業化 UI 佈局
# ==========================================
APP_NAME = "超級績效 智能趨勢選股系統"
VERSION = "V28"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide", initial_sidebar_state="expanded")

# 隱藏預設裝飾線，維持彭博終端極致質感
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
div.block-container {padding-top: 1.5rem;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title(f"📈 {APP_NAME} {VERSION} (強固穩定版)")

# 初始化持久化記憶
if 'scan_df' not in st.session_state:
    st.session_state.scan_df = None
if 'active_tickers' not in st.session_state:
    st.session_state.active_tickers = []

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

st.sidebar.markdown("---")
if st.sidebar.button("♻️ 強制清空緩存並重整", use_container_width=True):
    st.cache_data.clear()
    st.session_state.scan_df = None
    st.session_state.active_tickers = []
    st.rerun()

# ==========================================
# 2. 數據抓取引擎 (導入 API 斷鏈免疫機制)
# ==========================================

@st.cache_data(ttl=86400)
def fetch_full_sp500_data():
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
        
        # 技術指標計算 (核心過濾基礎)
        df['50MA'] = df['Close'].rolling(50).mean()
        df['150MA'] = df['Close'].rolling(150).mean()
        df['200MA'] = df['Close'].rolling(200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(50).mean()
        
        # 獨立 Try-Except 斷開連鎖崩潰：即使 API 阻擋 info，仍保留 K 線成果
        eps_val, rev_val = 0.0, 0.0
        try:
            info = s.info
            eps_val = (info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth') or 0) * 100
            rev_val = (info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth') or 0) * 100
        except:
            pass # 靜默通過，依賴純量價趨勢過濾
            
        fund = {"eps": eps_val, "rev": rev_val}
        return df, fund
    except: return None, None

# ==========================================
# 3. 掃描器頁面
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 批量趨勢篩選雷達")
    
    sp_data, all_sectors = fetch_full_sp500_data()

    with st.container():
        c1, c2, c3 = st.columns([1.2, 1.5, 1.3])
        with c1:
            mode = st.radio("掃描範圍選擇：", [
                "🔥 熱門精選 (22檔)", 
                "🇺🇸 標普 500 全掃", 
                "📂 標普 500 分板塊", 
                "✍️ 自訂輸入清單"
            ])
        with c2:
            if mode == "📂 標普 500 分板塊":
                target_sector = st.selectbox("🎯 選擇目標板塊：", all_sectors)
            elif mode == "✍️ 自訂輸入清單":
                custom_input = st.text_area("⌨️ 輸入股票代號 (以逗號隔開)：", "LITE, COHR, NVDA, TSLA, APP", height=100)
            else:
                st.info("💡 系統將自動載入大數據清單進行量價與趨勢解析。")
                
        with c3:
            sort_key = st.selectbox("📊 結果排序依據：", ["綜合潛力", "RS強度", "EPS成長", "營收成長"])
            min_s = st.slider("🎯 趨勢技術得分門檻：", 4, 7, 7)
            only_rs = st.checkbox("👑 嚴格過濾：僅顯示跑贏大盤 (RS > 0)", value=True)

    st.markdown("---")
    if st.button("🏁 啟動量價與動能深度掃描", type="primary", use_container_width=True):
        if mode == "🔥 熱門精選 (22檔)":
            tickers = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "COHR", "PLTR", "ARM", "AVGO", "NFLX", "SMCI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT", "AMD", "TSM", "SOFI"]
        elif mode == "🇺🇸 標普 500 全掃":
            tickers = sp_data['Symbol'].tolist() if not sp_data.empty else []
        elif mode == "📂 標普 500 分板塊":
            tickers = sp_data[sp_data['GICS Sector'] == target_sector]['Symbol'].tolist() if not sp_data.empty else []
        else:
            tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]

        if not tickers:
            st.error("❌ 掃描清單為空，請確認代號或網路狀態。")
        else:
            results = []
            bar = st.progress(0)
            status = st.empty()

            for i, t in enumerate(tickers):
                status.text(f"⏳ 終端運算中 ({i+1}/{len(tickers)}): 正在萃取 {t} 量價結構...")
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
                            "綜合潛力": round(potential, 1), "最新價格": round(cur, 2),
                            "EPS成長(%)": round(fund['eps'], 1), "營收成長(%)": round(fund['rev'], 1)
                        })
                bar.progress((i + 1) / len(tickers))
            
            status.empty()
            if results:
                st.session_state.scan_df = pd.DataFrame(results).sort_values(by=sort_key, ascending=False)
                st.session_state.active_tickers = st.session_state.scan_df['代號'].tolist()
                st.success(f"🎯 掃描完成！成功鎖定 {len(results)} 檔多頭趨勢股。")
            else:
                st.session_state.scan_df = None
                st.warning("⚠️ 當前門檻下無標的達標。若剛執行過大掃描，Yahoo API 可能暫時限制連線，但技術面過濾引擎仍正常運作。")

    if st.session_state.scan_df is not None:
        st.markdown("##### 終端輸出矩陣 (Data Matrix)")
        st.dataframe(
            st.session_state.scan_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "最新價格": st.column_config.NumberColumn(format="$%.2f"),
                "綜合潛力": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100),
                "RS強度": st.column_config.NumberColumn(format="%.1f%%")
            }
        )

# ==========================================
# 4. 個股深度分析頁面
# ==========================================
else:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 目標載入指定")
    
    target_source = st.sidebar.radio("連動通道：", ["清單快速切換", "手動獨立查詢"])
    
    if target_source == "清單快速切換":
        if st.session_state.active_tickers:
            target = st.sidebar.selectbox("檢視掃描成果：", st.session_state.active_tickers)
        else:
            st.sidebar.warning("暫無掃描快取，請輸入代號。")
            target = "NVDA"
    else:
        target = st.sidebar.text_input("✍️ 鍵入特定代號：", value="LITE").upper()
    
    df, fund = get_sepa_data(target)
    if df is not None:
        st.subheader(f"📊 {target} 動能型態與多空版圖")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("即時定價", f"${df['Close'].iloc[-1]:.2f}", f"{df['Close'].iloc[-1] - df['Close'].iloc[-2]:+.2f}")
        c2.metric("RS 強度 (超額表現)", f"{((df['Close'].iloc[-1]/df['Close'].iloc[-126])-1-SPY_6M)*100:.1f}%")
        c3.metric("季度 EPS 動能", f"{fund['eps']:.1f}%")
        c4.metric("季度營收推力", f"{fund['rev']:.1f}%")
        
        st.markdown("---")
        tabs = st.tabs(["日K 決策視角", "周K 波段視角", "月K 宏觀視角"])
        
        def plot_professional(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            d = data.tail(252) if len(data) > 252 else data
            
            fig.add_trace(go.Candlestick(x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'], name='定價'), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['50MA'], name='50MA (短防)', line=dict(color='#00E5FF', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['150MA'], name='150MA (趨勢)', line=dict(color='#FFD700', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['200MA'], name='200MA (牛熊)', line=dict(color='#FF1744', width=1.5)), row=1, col=1)
            
            cols = ['#FF5252' if r['Open'] > r['Close'] else '#00E676' for _, r in d.iterrows()]
            fig.add_trace(go.Bar(x=d.index, y=d['Volume'], name='籌碼量能', marker_color=cols), row=2, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d['Vol_50MA'], name='50均量基準', line=dict(color='#FF9100', width=1.2)), row=2, col=1)
            
            fig.update_layout(
                height=720, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified",
                margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#0E1117", plot_bgcolor="#0E1117"
            )
            fig.update_xaxes(showgrid=True, gridcolor='#1F2430', zeroline=False)
            fig.update_yaxes(showgrid=True, gridcolor='#1F2430', zeroline=False)
            return fig
        
        with tabs[0]: st.plotly_chart(plot_professional(df), use_container_width=True)
        with tabs[1]:
            w = yf.Ticker(target).history(period="5y", interval="1wk")
            if not w.empty:
                for ma in [50, 150, 200]: w[f'{ma}MA'] = w['Close'].rolling(ma).mean()
                w['Vol_50MA'] = w['Volume'].rolling(50).mean()
                st.plotly_chart(plot_professional(w), use_container_width=True)
        with tabs[2]:
            m_data = yf.Ticker(target).history(period="max", interval="1mo")
            if not m_data.empty:
                for ma in [50, 150, 200]: m_data[f'{ma}MA'] = m_data['Close'].rolling(ma).mean()
                m_data['Vol_50MA'] = m_data['Volume'].rolling(50).mean()
                st.plotly_chart(plot_professional(m_data), use_container_width=True)
    else:
        st.error("❌ 數據解析中斷，請確認輸入正確或點擊側邊欄『強制清空緩存』重置連線。")
