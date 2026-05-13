import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# ==========================================
# 系統設定與品牌命名
# ==========================================
APP_NAME = "超級績效智能趨勢選股系統"
VERSION = "V15"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION}")

# --- 側邊欄：智能導覽 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

# 預設的高質量美股觀察池 (不含港股)
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# --- 核心數據引擎：GitHub CDN 讀取 S&P 500 ---
@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    try:
        # 使用最高穩定性的原始數據源，避免網頁變動導致出錯
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except Exception:
        return TECH_GIANTS + GROWTH_STARS

@st.cache_data(ttl=3600)
def load_stock_data(ticker, period="2y", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty and len(df) >= 200:
            # 專業均線運算
            df['50MA'] = df['Close'].rolling(window=50).mean()
            df['150MA'] = df['Close'].rolling(window=150).mean()
            df['200MA'] = df['Close'].rolling(window=200).mean()
            df['MA200_Past'] = df['200MA'].shift(20)
            df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
            return df
    except: pass
    return pd.DataFrame()

def run_screener_logic(df):
    if df.empty or len(df) < 200: return 0, False, {}
    cur_p = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    hi52 = float(df.tail(252)['High'].max())
    lo52 = float(df.tail(252)['Low'].min())
    
    # 七大核心趨勢篩選準則
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
# 頁面一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹超級績效全市場掃描雷達")
    st.write("自動鎖定美股全市場，捕捉處於第二階段 (Stage 2) 的超級成長股。")
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        pool_choice = st.radio(
            "請選擇自動掃描範圍：",
            [
                "🌟 美股核心科技巨頭 (11檔)",
                "🔥 高成長強勢股清單 (11檔)",
                "🇺🇸 標普 500 前 50 檔熱門權值股",
                "🇺🇸 標普 500 前 100 檔熱門權值股",
                "🇺🇸 標普 500 全成份股掃描 (約500檔)",
                "✍️ 自訂代號手動掃描"
            ]
        )
    with col_sel2:
        target_score = st.slider("篩選門檻 (得分越高越強勢)：", 4, 7, 6)

    if st.button("🏁 啟動全自動趨勢掃描", type="primary"):
        sp500_all = fetch_sp500_tickers()
        if pool_choice == "🌟 美股核心科技巨頭 (11檔)": scan_list = TECH_GIANTS
        elif pool_choice == "🔥 高成長強勢股清單 (11檔)": scan_list = GROWTH_STARS
        elif "前 50 檔" in pool_choice: scan_list = sp500_all[:50]
        elif "前 100 檔" in pool_choice: scan_list = sp500_all[:100]
        elif "全成份股" in pool_choice: scan_list = sp500_all
        else:
            custom_str = st.text_area("自訂掃描代號 (逗號隔開)", "COHR, NVDA, PLTR, TSM")
            scan_list = [t.strip().upper() for t in custom_str.split(",") if t.strip()]

        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(scan_list):
            status.text(f"正在掃描 ({i+1}/{len(scan_list)}): {t}")
            df = load_stock_data(t)
            if not df.empty:
                score, is_pass, m = run_screener_logic(df)
                if score >= target_score:
                    results.append({
                        "股票代號": t, 
                        "健檢總分": f"{score} / 7", 
                        "趨勢狀態": "🔥 符合 Stage 2" if is_pass else "結構轉強中",
                        "最新價": f"${m['price']:.2f}", 
                        "距52週高點": f"{((m['price']/m['hi52'])-1)*100:.1f}%"
                    })
            progress.progress((i + 1) / len(scan_list))
        
        status.success(f"任務完成！已掃描 {len(scan_list)} 檔標的，為您挑選出 {len(results)} 檔達標個股。")
        if results:
            st.table(pd.DataFrame(results))
        else:
            st.warning("目前範圍內無標的符合該門檻條件。")

# ==========================================
# 頁面二：📊 個股深度分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 個股搜索")
    input_type = st.sidebar.radio("選股方式", ["下拉快速切換", "手動輸入代號"])
    
    combined_list = TECH_GIANTS + GROWTH_STARS
    ticker = st.sidebar.selectbox("選取標的", combined_list) if input_type == "下拉快速切換" else st.sidebar.text_input("輸入美股代號", value="COHR").upper()
    
    df_daily = load_stock_data(ticker)
    if not df_daily.empty:
        score, is_pass, m = run_screener_logic(df_daily)
        
        # 頂部儀表板
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前價格", f"${m['price']:.2f}")
        c2.metric("52週最高", f"${m['hi52']:.2f}")
        c3.metric("52週最低", f"${m['lo52']:.2f}")
        c4.metric("趨勢綜合評分", f"{score} / 7")
        
        # 常駐健檢清單
        st.markdown("---")
        st.subheader("📋 第二階段 (Stage 2) 技術面健檢清單")
        l_col, r_col = st.columns([2, 1])
        with l_col:
            last = df_daily.iloc[-1]
            st.write(f"{'✅' if m['price'] > last['150MA'] and m['price'] > last['200MA'] else '❌'} 價格高於 150MA 與 200MA (底部支撐牢固)")
            st.write(f"{'✅' if last['150MA'] > last['200MA'] else '❌'} 150MA 高於 200MA (多頭趨勢確立)")
            st.write(f"{'✅' if last['200MA'] > df_daily['MA200_Past'].iloc[-1] else '❌'} 200MA 趨勢向上 (長線動能轉強)")
            st.write(f"{'✅' if last['50MA'] > last['150MA'] and last['50MA'] > last['200MA'] else '❌'} 50MA 高於長線均線 (中線動能加速)")
            st.write(f"{'✅' if m['price'] > last['50MA'] else '❌'} 價格回測 50MA 不破 (短線強勢)")
            st.write(f"{'✅' if m['price'] > m['lo52']*1.3 else '❌'} 比 52 週最低點高出至少 30%")
            st.write(f"{'✅' if m['price'] > m['hi52']*0.75 else '❌'} 距離 52 週最高點在 25% 以內 (高位震盪整理)")
        with r_col:
            if is_pass: st.success(f"💎 **{ticker} 目前展現極致強勢，完全符合超級績效模板！**")
            else: st.warning(f"目前滿足 {score} 項條件，請觀察關鍵指標的修復狀況。")
        st.markdown("---")
        
        # 看盤分頁
        t1, t2, t3 = st.tabs(["日K 走勢", "周K 走勢", "月K 走勢"])
        def draw_chart(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA (藍)', line=dict(color='blue', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA (黃)', line=dict(color='yellow', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA (紅)', line=dict(color='red', width=1.5)), row=1, col=1)
            vol_colors = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.6)')), row=2, col=1)
            fig.update_layout(height=650, xaxis_rangeslider_visible=False, template="plotly_dark", hovermode="x unified")
            fig.update_xaxes(showgrid=True, gridcolor='#2a2a2a')
            fig.update_yaxes(showgrid=True, gridcolor='#2a2a2a')
            return fig

        with t1: st.plotly_chart(draw_chart(df_daily), use_container_width=True)
        with t2:
            w_data = load_stock_data(ticker, "5y", "1wk")
            if not w_data.empty: st.plotly_chart(draw_chart(w_data), use_container_width=True)
        with t3:
            m_data = load_stock_data(ticker, "max", "1mo")
            if not m_data.empty: st.plotly_chart(draw_chart(m_data), use_container_width=True)
    else:
        st.error("查無資料，請確認代號是否正確。")
