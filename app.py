import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# ==========================================
# 系統設定與品牌命名
# ==========================================
APP_NAME = "鷹眼 (EagleEye) 智能趨勢選股系統"
VERSION = "V18"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION}")

# --- 側邊欄：控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.rerun()

# 預設標的池
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# --- 核心引擎：資料抓取 ---
@st.cache_data(ttl=3600)
def fetch_sp500_list():
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return TECH_GIANTS + GROWTH_STARS

@st.cache_data(ttl=3600)
def get_stock_data_v18(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return pd.DataFrame(), {}
        
        info = {}
        try:
            info = stock.info
        except: pass
        
        # 計算均線
        df['50MA'] = df['Close'].rolling(50).mean()
        df['150MA'] = df['Close'].rolling(150).mean()
        df['200MA'] = df['Close'].rolling(200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(50).mean()
        
        eps_g = info.get('earningsQuarterlyGrowth')
        rev_g = info.get('revenueGrowth')
        
        return df, {"eps": eps_g * 100 if eps_g else None, "rev": rev_g * 100 if rev_g else None}
    except:
        return pd.DataFrame(), {}

# --- 繪圖函數 ---
def draw_professional_chart(data, title_prefix=""):
    if data.empty: return None
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
    
    # K線與均線
    df_plot = data.tail(252) if len(data) > 252 else data
    fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50MA', line=dict(color='blue', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], name='150MA', line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], name='200MA', line=dict(color='red', width=2)), row=1, col=1)
    
    # 成交量
    colors = ['#ff4a4a' if row['Open'] > row['Close'] else '#00c873' for _, row in df_plot.iterrows()]
    fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='成交量', marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Vol_50MA'], name='均量', line=dict(color='rgba(255, 255, 255, 0.5)')), row=2, col=1)
    
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=True)
    fig.update_xaxes(showgrid=True, gridcolor='#333')
    fig.update_yaxes(showgrid=True, gridcolor='#333')
    return fig

# ==========================================
# 模式一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼全市場掃描雷達")
    col1, col2 = st.columns(2)
    with col1:
        pool_choice = st.radio("掃描範圍：", ["🔥 熱門精選 (22檔)", "🇺🇸 標普 500 前 100 檔", "🇺🇸 標普 500 全成份股"])
    with col2:
        score_limit = st.slider("技術面門檻分數：", 4, 7, 6)
        filter_growth = st.checkbox("📈 僅顯示財報正成長 (有資料才過濾)", value=False)

    if st.button("🏁 啟動深度掃描", type="primary"):
        all_list = fetch_sp500_list()
        scan_list = (TECH_GIANTS + GROWTH_STARS) if "熱門" in pool_choice else (all_list[:100] if "100" in pool_choice else all_list)

        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, t in enumerate(scan_list):
            status.text(f"掃描中 ({i+1}/{len(scan_list)}): {t}")
            df, fund = get_stock_data_v18(t)
            if not df.empty:
                cur = df['Close'].iloc[-1]
                m50, m150, m200 = df['50MA'].iloc[-1], df['150MA'].iloc[-1], df['200MA'].iloc[-1]
                h52, l52 = df['High'].tail(252).max(), df['Low'].tail(252).min()
                score = sum([cur > m150 and cur > m200, m150 > m200, m200 > df['200MA'].iloc[-20], m50 > m150, cur > m50, cur > l52 * 1.3, cur > h52 * 0.75])
                
                eps_v, rev_v = fund.get('eps'), fund.get('rev')
                if score >= score_limit:
                    if filter_growth and ((eps_v and eps_v < 0) or (rev_v and rev_v < 0)): continue
                    results.append({"代號": t, "得分": f"{score}/7", "價格": f"${cur:.2f}", "EPS成長": f"{eps_v:.1f}%" if eps_v else "-", "營收成長": f"{rev_v:.1f}%" if rev_v else "-"})
            progress.progress((i + 1) / len(scan_list))
        
        status.success(f"完成！共發現 {len(results)} 檔符合條件的股票。")
        if results: st.dataframe(pd.DataFrame(results), use_container_width=True)

# ==========================================
# 模式二：📊 個股深度分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    ticker = st.sidebar.text_input("🎯 輸入美股代號", value="NVDA").upper()
    
    if ticker:
        df, fund = get_stock_data_v18(ticker)
        if not df.empty:
            # 頂部儀表板
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("當前價格", f"${df['Close'].iloc[-1]:.2f}")
            c2.metric("EPS 季度成長", f"{fund['eps']:.1f}%" if fund['eps'] else "N/A")
            c3.metric("營收季度成長", f"{fund['rev']:.1f}%" if fund['rev'] else "N/A")
            c4.metric("50MA 狀態", "高於" if df['Close'].iloc[-1] > df['50MA'].iloc[-1] else "低於")
            
            # 趨勢健檢
            st.markdown("---")
            st.subheader(f"📊 {ticker} 超級績效趨勢圖表")
            
            t1, t2, t3 = st.tabs(["日K 線圖", "周K 線圖", "月K 線圖"])
            
            with t1:
                st.plotly_chart(draw_professional_chart(df), use_container_width=True)
            
            with t2:
                # 重新抓取週線數據
                w_stock = yf.Ticker(ticker)
                w_df = w_stock.history(period="5y", interval="1wk")
                if not w_df.empty:
                    w_df['50MA'] = w_df['Close'].rolling(50).mean()
                    w_df['150MA'] = w_df['Close'].rolling(150).mean()
                    w_df['200MA'] = w_df['Close'].rolling(200).mean()
                    w_df['Vol_50MA'] = w_df['Volume'].rolling(50).mean()
                    st.plotly_chart(draw_professional_chart(w_df), use_container_width=True)
            
            with t3:
                # 重新抓取月線數據
                m_stock = yf.Ticker(ticker)
                m_df = m_stock.history(period="max", interval="1mo")
                if not m_df.empty:
                    m_df['50MA'] = m_df['Close'].rolling(50).mean()
                    m_df['150MA'] = m_df['Close'].rolling(150).mean()
                    m_df['200MA'] = m_df['Close'].rolling(200).mean()
                    m_df['Vol_50MA'] = m_df['Volume'].rolling(50).mean()
                    st.plotly_chart(draw_professional_chart(m_df), use_container_width=True)
        else:
            st.error("查無資料，請檢查代號是否輸入正確。")
