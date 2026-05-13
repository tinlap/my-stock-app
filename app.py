import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import datetime

# 設定網頁標題
st.set_page_config(page_title="Minervini 全自動掃描王 V10", layout="wide")
st.title("🦅 Mark Minervini 全自動美股掃描系統")

# --- 側邊欄：功能切換 ---
st.sidebar.header("系統選單")
page_mode = st.sidebar.radio("切換模式", ["🔍 全自動選股掃描器", "📊 個股詳細分析"])

# --- 核心引擎：自動抓取標普 500 名單 ---
@st.cache_data(ttl=86400) # 一天更新一次名單即可
def get_sp500_tickers():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)
        df = table[0]
        return df['Symbol'].tolist()
    except:
        return ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA"] # 備用名單

# --- 核心引擎：數據處理與篩選邏輯 ---
@st.cache_data(ttl=3600)
def fetch_and_analyze(ticker):
    try:
        data = yf.download(ticker, period="2y", interval="1d", progress=False)
        if data.empty or len(data) < 250:
            return None
        
        # 計算指標
        close = data['Close']
        ma50 = close.rolling(window=50).mean()
        ma150 = close.rolling(window=150).mean()
        ma200 = close.rolling(window=200).mean()
        
        cur_p = float(close.iloc[-1])
        m50, m150, m200 = float(ma50.iloc[-1]), float(ma150.iloc[-1]), float(ma200.iloc[-1])
        m200_past = float(ma200.iloc[-20])
        
        hi52 = float(data['High'].tail(252).max())
        lo52 = float(data['Low'].tail(252).min())
        
        # Mark Minervini 7大條件
        conds = [
            cur_p > m150 and cur_p > m200,      # 1. 價格在150/200MA之上
            m150 > m200,                         # 2. 150MA > 200MA
            m200 > m200_past,                    # 3. 200MA 趨勢向上
            m50 > m150 and m50 > m200,           # 4. 50MA > 150/200MA
            cur_p > m50,                         # 5. 價格在50MA之上
            cur_p > lo52 * 1.3,                  # 6. 比52週低點高30%
            cur_p > hi52 * 0.75                  # 7. 距離52週高點25%以內
        ]
        
        score = sum(conds)
        return {
            "代號": ticker,
            "得分": score,
            "價格": round(cur_p, 2),
            "52週高點距離": f"{round((cur_p/hi52 - 1)*100, 1)}%",
            "52週低點距離": f"{round((cur_p/lo52 - 1)*100, 1)}%",
            "狀態": "🔥 符合 Stage 2" if score == 7 else "觀察中"
        }
    except:
        return None

# ==========================================
# 模式一：全自動選股掃描器
# ==========================================
if page_mode == "🔍 全自動選股掃描器":
    st.subheader("🚀 標普 500 (S&P 500) 實時強勢股掃描")
    
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        pool_size = st.selectbox("選擇掃描範圍", ["前 50 隻熱門股", "前 100 隻熱門股", "全 500 隻成份股 (需較長時間)"])
    with col_ctrl2:
        min_score_target = st.slider("顯示得分高於多少的股票", 4, 7, 6)

    if st.button("🏁 開始全自動掃描", type="primary"):
        all_tickers = get_sp500_tickers()
        
        # 根據選擇調整數量
        limit = 50 if "50 隻" in pool_size else 100 if "100 隻" in pool_size else 500
        scan_list = all_tickers[:limit]
        
        results = []
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(scan_list):
            status.text(f"正在掃描 ({i+1}/{len(scan_list)}): {t}")
            res = fetch_and_analyze(t)
            if res and res['得分'] >= min_score_target:
                results.append(res)
            progress_bar.progress((i + 1) / len(scan_list))
            
        status.success(f"掃描完成！在 {len(scan_list)} 隻標的中找到了 {len(results)} 隻強勢股。")
        
        if results:
            final_df = pd.DataFrame(results).sort_values(by="得分", ascending=False)
            st.table(final_df) # 使用表格顯示，清清楚楚
        else:
            st.warning("目前沒有股票符合這麼高的分數條件。")

# ==========================================
# 模式二：個股詳細分析 (保留你原本最愛的牛牛風格圖表)
# ==========================================
else:
    st.sidebar.markdown("---")
    ticker = st.sidebar.text_input("輸入代號查看細節", value="NVDA").upper()
    
    # 這裡放你原本 V9 版本的繪圖與健檢清單代碼... (為了節省篇幅，建議直接保留原繪圖邏輯)
    st.info(f"正在載入 {ticker} 的詳細 K 線與均線圖表...")
    # (載入數據與繪圖邏輯與 V9 相同)
