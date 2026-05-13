import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# ==========================================
# 1. 系統設定
# ==========================================
APP_NAME = "鷹眼 (EagleEye) 智能趨勢選股系統"
VERSION = "V21"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION}")

# 初始化 Session State，用於跨頁面傳遞掃描結果
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = []

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.session_state.scan_results = []
    st.rerun()

# --- 核心引擎 ---
@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "COHR", "PLTR"]

@st.cache_data(ttl=3600)
def get_stock_data_v21(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return pd.DataFrame(), {}
        
        info = {}
        try: info = stock.info
        except: pass
        
        # 指標計算
        df['50MA'] = df['Close'].rolling(50).mean()
        df['150MA'] = df['Close'].rolling(150).mean()
        df['200MA'] = df['Close'].rolling(200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(50).mean()
        
        eps_g = info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth')
        rev_g = info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth')
        
        return df, {
            "eps": eps_g * 100 if eps_g else 0,
            "rev": rev_g * 100 if rev_g else 0
        }
    except: return pd.DataFrame(), {}

def evaluate_v21(df, fund):
    cur = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    h52, l52 = float(df.tail(252)['High'].max()), float(df.tail(252)['Low'].min())
    
    c1 = cur > last['150MA'] and cur > last['200MA']
    c2 = last['150MA'] > last['200MA']
    c3 = last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False
    c4 = last['50MA'] > last['150MA'] and last['50MA'] > last['200MA']
    c5 = cur > last['50MA']
    c6 = cur > l52 * 1.3
    c7 = cur > h52 * 0.75
    score = sum([c1, c2, c3, c4, c5, c6, c7])
    
    return score, (score == 7), {"price": cur, "eps": fund.get('eps', 0), "rev": fund.get('rev', 0)}

# ==========================================
# 3. 掃描器模式 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼全市場掃描雷達")
    
    col_a, col_b = st.columns(2)
    with col_a:
        pool = st.radio("範圍：", ["🔥 熱門精選", "🇺🇸 標普 500 全部", "✍️ 自訂輸入"])
    with col_b:
        min_s = st.slider("最低門檻：", 4, 7, 7)
        f_growth = st.checkbox("📈 僅顯示財報正成長", value=False)

    if st.button("🏁 啟動全方位掃描", type="primary"):
        tickers = fetch_sp500_tickers() if "標普" in pool else ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "COHR", "PLTR"]
        
        results = []
        bar = st.progress(0)
        status = st.empty()

        for i, t in enumerate(tickers):
            status.text(f"掃描中 ({i+1}/{len(tickers)}): {t}")
            df, fund = get_stock_data_v21(t)
            if not df.empty:
                score, is_pass, m = evaluate_v21(df, fund)
                growth_ok = (m['eps'] > 0 or m['rev'] > 0) if f_growth else True
                
                if score >= min_s and growth_ok:
                    results.append({
                        "代號": t, "得分": score, "狀態": "🔥 符合" if is_pass else "蓄勢",
                        "價格": m['price'], "EPS成長(%)": round(m['eps'], 1), "營收成長(%)": round(m['rev'], 1)
                    })
            bar.progress((i + 1) / len(tickers))
        
        st.session_state.scan_results = [r['代號'] for r in results]
        status.success(f"完成！找到 {len(results)} 檔個股。提示：可點擊下方表頭進行排序。")
        
        if results:
            # 使用 st.dataframe 替代 st.table，支援點擊表頭排序
            st.dataframe(
                pd.DataFrame(results).sort_values(by="EPS成長(%)", ascending=False),
                use_container_width=True,
                hide_index=True
            )
            st.info("💡 掃描完畢！現在可切換到『個股深度分析』，從下拉選單直接查看上述標的圖表。")

# ==========================================
# 4. 圖表模式 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    if st.session_state.scan_results:
        # 連動功能：直接從掃描結果中選取
        ticker = st.sidebar.selectbox("🎯 快速查看掃描結果", st.session_state.scan_results)
    else:
        ticker = st.sidebar.text_input("🎯 手動輸入代號", value="NVDA").upper()
    
    df, fund = get_stock_data_v21(ticker)
    if not df.empty:
        score, is_pass, m = evaluate_v21(df, fund)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("價格", f"${m['price']:.2f}")
        c2.metric("得分", f"{score}/7")
        c3.metric("EPS成長", f"{m['eps']:.1f}%")
        c4.metric("營收成長", f"{m['rev']:.1f}%")
        
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
        # (周K與月K邏輯同前，為簡潔省略)
