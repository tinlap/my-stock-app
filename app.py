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
VERSION = "V17"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION} (穩定性增強版)")

# --- 側邊欄：控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

# 強制重新整理按鈕 (解決你遇到的緩存問題)
if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.rerun()

# 預設標的池
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# --- 核心引擎：資料抓取 (加入異常處理機制) ---
@st.cache_data(ttl=3600)
def fetch_sp500_list():
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return TECH_GIANTS + GROWTH_STARS

@st.cache_data(ttl=3600)
def get_stock_data_v17(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取歷史K線
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return pd.DataFrame(), {}
        
        # 抓取財報 (改為更穩定的 key 抓取)
        info = {}
        try:
            info = stock.fast_info # 先拿快訊
            full_info = stock.info # 再試圖拿財報
            info.update(full_info)
        except: pass
        
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

# ==========================================
# 模式一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼全市場掃描雷達")
    
    col1, col2 = st.columns(2)
    with col1:
        pool_choice = st.radio("掃描範圍：", ["🔥 熱門精選 (22檔)", "🇺🇸 標普 500 前 100 檔", "🇺🇸 標普 500 全成份股", "✍️ 自訂輸入"])
    with col2:
        score_limit = st.slider("技術面門檻分數：", 4, 7, 6)
        filter_growth = st.checkbox("📈 僅顯示財報正成長 (若 API 失敗則暫跳過)", value=False)

    if st.button("🏁 啟動深度掃描", type="primary"):
        all_list = fetch_sp500_list()
        if "熱門精選" in pool_choice: scan_list = TECH_GIANTS + GROWTH_STARS
        elif "100 檔" in pool_choice: scan_list = all_list[:100]
        elif "全成份股" in pool_choice: scan_list = all_list
        else: scan_list = ["NVDA", "COHR", "GOOG"] # 範例

        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, t in enumerate(scan_list):
            status.text(f"掃描中 ({i+1}/{len(scan_list)}): {t}")
            df, fund = get_stock_data_v17(t)
            
            if not df.empty:
                cur = df['Close'].iloc[-1]
                m50, m150, m200 = df['50MA'].iloc[-1], df['150MA'].iloc[-1], df['200MA'].iloc[-1]
                m200_p = df['MA200_Past'].iloc[-1]
                h52, l52 = df['High'].tail(252).max(), df['Low'].tail(252).min()
                
                conds = [
                    cur > m150 and cur > m200, m150 > m200, m200 > m200_p,
                    m50 > m150 and m50 > m200, cur > m50,
                    cur > l52 * 1.3, cur > h52 * 0.75
                ]
                score = sum(conds)
                
                # 財報判斷邏輯優化
                eps_v = fund.get('eps')
                rev_v = fund.get('rev')
                is_growing = (eps_v and eps_v > 0) or (rev_v and rev_v > 0)
                
                # 如果使用者沒勾選成長過濾，或者 API 沒給數據但技術面很強，我們依然保留它
                if score >= score_limit:
                    if filter_growth and not is_growing and (eps_v is not None or rev_v is not None):
                        continue # 只有明確為負成長才剔除
                    
                    results.append({
                        "代號": t, "得分": f"{score}/7",
                        "價格": f"${cur:.2f}",
                        "EPS成長": f"{eps_v:.1f}%" if eps_v else "API未響應",
                        "營收成長": f"{rev_v:.1f}%" if rev_v else "API未響應"
                    })
            progress.progress((i + 1) / len(scan_list))
        
        status.success(f"完成！共發現 {len(results)} 檔符合條件的股票。")
        if results: st.table(pd.DataFrame(results))

# ==========================================
# 模式二：📊 個股詳細分析 (Chart)
# ==========================================
else:
    ticker = st.sidebar.text_input("輸入美股代號", value="NVDA").upper()
    df, fund = get_stock_data_v17(ticker)
    if not df.empty:
        # (此處保留 V16 的繪圖代碼即可)
        st.write(f"### {ticker} 詳細分析")
        st.metric("最新價", f"${df['Close'].iloc[-1]:.2f}")
        # ... (繪圖邏輯)
