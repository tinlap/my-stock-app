import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. 頁面基礎設定
st.set_page_config(page_title="Minervini 終極選股看盤系統", layout="wide")
st.title("🦅 Mark Minervini 智能選股與專業看盤系統")

# --- 側邊欄導覽 ---
st.sidebar.header("系統導覽")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股詳細分析 (Chart)"])

# 預設的高質量觀察池
DEFAULT_WATCHLIST = ["COHR", "NVDA", "GOOG", "SOFI", "AAPL", "TSLA", "TSM", "PLTR", "0700.HK"]

# --- 核心引擎：資料抓取與處理 ---
@st.cache_data(ttl=3600)
def load_stock_data(ticker, period="2y", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty and len(df) >= 200:
            df['50MA'] = df['Close'].rolling(window=50).mean()
            df['150MA'] = df['Close'].rolling(window=150).mean()
            df['200MA'] = df['Close'].rolling(window=200).mean()
            df['MA200_Past'] = df['200MA'].shift(20)
            df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
            return df
    except:
        pass
    return pd.DataFrame()

def run_screener_logic(df):
    """計算 Mark Minervini 7 大指標並回傳分數"""
    if df.empty or len(df) < 200: return 0, False, {}
    cur_p = df['Close'].iloc[-1]
    last = df.iloc[-1]
    hi52 = df.tail(252)['High'].max()
    lo52 = df.tail(252)['Low'].min()
    
    c1 = cur_p > last['150MA'] and cur_p > last['200MA']
    c2 = last['150MA'] > last['200MA']
    c3 = last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False
    c4 = last['50MA'] > last['150MA'] and last['50MA'] > last['200MA']
    c5 = cur_p > last['50MA']
    c6 = cur_p > lo52 * 1.3
    c7 = cur_p > hi52 * 0.75
    
    score = sum([c1, c2, c3, c4, c5, c6, c7])
    return score, (score == 7), {"price": cur_p, "hi52": hi52, "lo52": lo52}

# ==========================================
# 模式一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 批量趨勢篩選雷達")
    st.write("請輸入你想掃描的股票池（用逗號隔開），系統將自動過濾出符合 Stage 2 的標的。")
    
    # 讓使用者輸入代號池，預設放一些熱門股
    pool_str = st.text_area("自訂掃描名單", value=", ".join(DEFAULT_WATCHLIST), height=100)
    target_score = st.slider("顯示得分不低於：", 4, 7, 6)
    
    if st.button("🏁 開始全自動掃描", type="primary"):
        tickers = [t.strip().upper() for t in pool_str.split(",") if t.strip()]
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(tickers):
            status.text(f"正在分析 ({i+1}/{len(tickers)}): {t}")
            df = load_stock_data(t)
            if not df.empty:
                score, is_pass, m = run_screener_logic(df)
                if score >= target_score:
                    results.append({
                        "代號": t, "得分": f"{score}/7", "狀態": "🔥 符合" if is_pass else "觀察中",
                        "價格": f"${m['price']:.2f}", "距高點": f"{((m['price']/m['hi52'])-1)*100:.1f}%"
                    })
            progress.progress((i + 1) / len(tickers))
        
        status.success(f"掃描完成！找到 {len(results)} 檔符合條件標的。")
        if results:
            st.table(pd.DataFrame(results))
        else:
            st.warning("目前沒有標的符合選定得分。")

# ==========================================
# 模式二：📊 個股詳細分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    input_type = st.sidebar.radio("標的選擇", ["快速下拉", "手動輸入"])
    ticker = st.sidebar.selectbox("選取股票", DEFAULT_WATCHLIST) if input_type == "快速下拉" else st.sidebar.text_input("輸入代號", value="COHR").upper()
    
    df_daily = load_stock_data(ticker)
    if not df_daily.empty:
        score, is_pass, m = run_screener_logic(df_daily)
        
        # 1. 頂部摘要
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("價格", f"${m['price']:.2f}")
        col2.metric("52週最高", f"${m['hi52']:.2f}")
        col3.metric("52週最低", f"${m['lo52']:.2f}")
        col4.metric("指標得分", f"{score} / 7")
        
        # 2. 常駐健檢清單 (不隱藏)
        st.markdown("---")
        st.subheader("📋 Stage 2 趨勢健檢詳細清單")
        c_list, c_msg = st.columns([2, 1])
        with c_list:
            last = df_daily.iloc[-1]
            st.write(f"{'✅' if m['price'] > last['150MA'] and m['price'] > last['200MA'] else '❌'} 價格 > 150MA & 200MA")
            st.write(f"{'✅' if last['150MA'] > last['200MA'] else '❌'} 150MA > 200MA")
            st.write(f"{'✅' if last['200MA'] > df_daily['MA200_Past'].iloc[-1] else '❌'} 200MA 趨勢向上")
            st.write(f"{'✅' if last['50MA'] > last['150MA'] and last['50MA'] > last['200MA'] else '❌'} 50MA > 150MA & 200MA")
            st.write(f"{'✅' if m['price'] > last['50MA'] else '❌'} 價格 > 50MA")
            st.write(f"{'✅' if m['price'] > m['lo52']*1.3 else '❌'} 脫離底部 30%")
            st.write(f"{'✅' if m['price'] > m['hi52']*0.75 else '❌'} 距高點 25% 以內")
        with c_msg:
            if is_pass: st.success("🔥 完全符合 Stage 2！")
            else: st.warning(f"目前符合 {score} 項條件。")
        st.markdown("---")
        
        # 3. 專業看盤區
        tabs = st.tabs(["日K", "周K", "月K"])
        def draw_chart(data, title):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA', line=dict(color='blue', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA', line=dict(color='yellow', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA', line=dict(color='red', width=1.5)), row=1, col=1)
            vol_colors = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.6)')), row=2, col=1)
            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", hovermode="x unified")
            return fig

        with tabs[0]: st.plotly_chart(draw_chart(df_daily, ticker), use_container_width=True)
        with tabs[1]:
            df_w = load_stock_data(ticker, "5y", "1wk")
            if not df_w.empty: st.plotly_chart(draw_chart(df_w, ticker), use_container_width=True)
        with tabs[2]:
            df_m = load_stock_data(ticker, "max", "1mo")
            if not df_m.empty: st.plotly_chart(draw_chart(df_m, ticker), use_container_width=True)
    else:
        st.error("查無資料，請確認代號是否正確。")
