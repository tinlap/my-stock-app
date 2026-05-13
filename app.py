import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 頁面基礎設定
st.set_page_config(page_title="Minervini 全自動看盤掃描系統", layout="wide")
st.title("🦅 Mark Minervini 智能選股與專業看盤系統")

# --- 側邊欄導覽 ---
st.sidebar.header("系統導覽")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股詳細分析 (Chart)"])

# 預設的分類精選股票池
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]
HK_STOCKS = ["0700.HK", "0388.HK", "3690.HK", "1299.HK", "0005.HK", "0941.HK", "1810.HK"]

# --- 自動抓取標普 500 最新成份股 ---
@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)
        return table[0]['Symbol'].tolist()
    except:
        return TECH_GIANTS + GROWTH_STARS

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
    if df.empty or len(df) < 200: return 0, False, {}
    cur_p = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    hi52 = float(df.tail(252)['High'].max())
    lo52 = float(df.tail(252)['Low'].min())
    
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
    st.subheader("🚀 批量趨勢篩選雷達 (免打字模式)")
    st.write("直接選擇內建的板塊名單，系統會全自動連線抓取並篩選出符合 Mark Minervini 第二階段的強勢股。")
    
    # 免打字選單設計
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        pool_choice = st.radio(
            "選擇要自動掃描的股票池：",
            [
                "🌟 美股熱門科技巨頭 (11檔)",
                "🔥 高動能高成長股 (11檔)",
                "🇭🇰 港股核心藍籌股精選 (7檔)",
                "🇺🇸 標普 500 前 50 檔權值股 (自動載入)",
                "🇺🇸 標普 500 前 100 檔權值股 (自動載入)",
                "✍️ 自訂代號 (手動模式)"
            ]
        )
    with col_sel2:
        target_score = st.slider("過濾標準：顯示得分不低於", 4, 7, 6)

    # 決定掃描名單
    if pool_choice == "🌟 美股熱門科技巨頭 (11檔)":
        scan_list = TECH_GIANTS
    elif pool_choice == "🔥 高動能高成長股 (11檔)":
        scan_list = GROWTH_STARS
    elif pool_choice == "🇭🇰 港股核心藍籌股精選 (7檔)":
        scan_list = HK_STOCKS
    elif "標普 500 前 50 檔" in pool_choice:
        scan_list = fetch_sp500_tickers()[:50]
    elif "標普 500 前 100 檔" in pool_choice:
        scan_list = fetch_sp500_tickers()[:100]
    else:
        custom_str = st.text_area("請輸入自訂代號 (以逗號隔開)", "COHR, NVDA, TSLA")
        scan_list = [t.strip().upper() for t in custom_str.split(",") if t.strip()]

    if st.button("🏁 啟動全自動掃描", type="primary"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(scan_list):
            status.text(f"正在連線分析 ({i+1}/{len(scan_list)}): {t} ...")
            df = load_stock_data(t)
            if not df.empty:
                score, is_pass, m = run_screener_logic(df)
                if score >= target_score:
                    results.append({
                        "代號": t, 
                        "健檢得分": f"{score} / 7", 
                        "Stage 2 狀態": "🔥 完美符合" if is_pass else "蓄勢中",
                        "最新收盤價": f"${m['price']:.2f}", 
                        "距52週高點": f"{((m['price']/m['hi52'])-1)*100:.1f}%"
                    })
            progress.progress((i + 1) / len(scan_list))
        
        status.success(f"掃描完成！在指定的 {len(scan_list)} 檔股票中挑選出 {len(results)} 檔達標強勢股。")
        if results:
            st.table(pd.DataFrame(results))
        else:
            st.warning("目前所選板塊中沒有符合該分數門檻的標的。")

# ==========================================
# 模式二：📊 個股詳細分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    st.sidebar.header("標的選擇")
    input_type = st.sidebar.radio("選擇方式", ["下拉快速切換", "手動輸入代號"])
    
    combined_list = TECH_GIANTS + GROWTH_STARS + HK_STOCKS
    if input_type == "下拉快速切換":
        ticker = st.sidebar.selectbox("選取股票", combined_list)
    else:
        ticker = st.sidebar.text_input("輸入代號 (港股加.HK)", value="COHR").upper()
    
    df_daily = load_stock_data(ticker)
    if not df_daily.empty:
        score, is_pass, m = run_screener_logic(df_daily)
        
        # 頂部數據
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("價格", f"${m['price']:.2f}")
        col2.metric("52週最高", f"${m['hi52']:.2f}")
        col3.metric("52週最低", f"${m['lo52']:.2f}")
        col4.metric("指標得分", f"{score} / 7")
        
        # 常駐健檢清單
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
        
        # 專業看盤區
        tabs = st.tabs(["日K", "周K", "月K"])
        def draw_chart(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA', line=dict(color='blue', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA', line=dict(color='yellow', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA', line=dict(color='red', width=1.5)), row=1, col=1)
            vol_colors = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.6)')), row=2, col=1)
            fig.update_layout(height=650, xaxis_rangeslider_visible=False, template="plotly_dark", hovermode="x unified")
            return fig

        with tabs[0]: st.plotly_chart(draw_chart(df_daily), use_container_width=True)
        with tabs[1]:
            df_w = load_stock_data(ticker, "5y", "1wk")
            if not df_w.empty: st.plotly_chart(draw_chart(df_w), use_container_width=True)
        with tabs[2]:
            df_m = load_stock_data(ticker, "max", "1mo")
            if not df_m.empty: st.plotly_chart(draw_chart(df_m), use_container_width=True)
    else:
        st.error("查無資料，請確認代號是否正確。")
