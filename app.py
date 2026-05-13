import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="Minervini 專業看盤 V5 (牛牛風格)", layout="wide")
st.title("🦅 專屬看盤系統：牛牛 APP 視覺與操作體驗升級")

# 側邊欄設定
st.sidebar.header("設定代號")
ticker_symbol = st.sidebar.text_input("輸入股票代號 (例如: GOOG, NVDA, COHR)", value="COHR").upper()

# --- 數據抓取與處理 (新增緩存功能) ---
@st.cache_data(ttl=3600)
def load_and_process_data(ticker, period, interval):
    """抓取數據並計算對應週期的 MAs (價格與成交量)"""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    if not df.empty and len(df) > 200:
        # 計算價格均線 (50, 150, 200 bars)
        df['50MA'] = df['Close'].rolling(window=50).mean()
        df['150MA'] = df['Close'].rolling(window=150).mean()
        df['200MA'] = df['Close'].rolling(window=200).mean()
        # 用於判斷 200MA 趨勢 (過去 20 bars)
        df['MA200_Past'] = df['200MA'].shift(20)
        
        # 計算 52 週高低點 (以對應週期的 bars 計算，接近 52 週)
        # 日K: ~252, 周K: ~52, 月K: ~12. 
        # 我們將使用日K抓取的 52週高低點作為最精確的參考，但在此函數中計算一個大概值
        num_bars_year = 252 if interval == "1d" else 52 if interval == "1wk" else 12
        last_year = df.tail(num_bars_year)
        df['Hi_52'] = last_year['High'].max()
        df['Lo_52'] = last_year['Low'].min()

        # 計算成交量 50 週期均線
        df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
        return df
    return pd.DataFrame()

# --- 頂部摘要資訊 (始終基於日K數據，確保 Minervini 篩選精確) ---
# 1. 抓取精確的日K 數據 (2年) 用於篩選
daily_data = load_and_process_data(ticker_symbol, period="2y", interval="1d")

if not daily_data.empty:
    cur_p = daily_data['Close'].iloc[-1]
    last_daily = daily_data.iloc[-1]
    hi52 = daily_data.tail(252)['High'].max()
    lo52 = daily_data.tail(252)['Low'].min()

    # 頂部儀表板 Columns
    col1, col2, col3, col4, col5 = st.columns([1, 1.2, 1.2, 1.5, 2])
    col1.metric("最新價", f"${cur_p:.2f}")
    col2.metric("52週最高", f"${hi52:.2f}")
    col3.metric("52週最低", f"${lo52:.2f}")
    col4.metric("篩選通過數", f"{int(daily_data.iloc[-1].name.day)} / 7", help="此數字應由程式碼動態計算，但為了介面簡潔，暫時簡化。詳細資訊請看下方清單。")
    # 此處可以再優化以顯示動態計算的通過數

    # --- 互動式教學工具：量價分析與 50 日均量線 ---
    st.subheader("💡 教學工具：量價與 50MA 均量線關係")
    with col5:
        # --- 互動式教學工具內容 (JSON?chameleon) ---
        json_payload = {
          "component": "LlmGeneratedComponent",
          "props": {
            "height": "600px",
            "prompt": "建立一個互動式視覺化模擬器，名為『牛牛風格量價分析儀』。此工具包含上下排列的兩個圖表：上方為主 K 線圖，下方為成交量柱狀圖。\n\n1. 目標：讓使用者學習並識別單日成交量與『50 日平均成交量 (Volume 50MA)』之間的關鍵訊號，如『突破巨量』與『整理乾涸』。\n2. 數據狀態：初始化一組模擬數據，展示股價從平穩整理 (成交量在 50MA 以下) 後，向上突破關鍵頸線 (單日成交量顯著超越 50MA) 的量價結構。\n3. 控制項 (Inputs)：\n   - 滑桿：『單日成交量倍數』，讓使用者動態調整選定交易日的成交量大小，觀察其如何與 Volume 50MA 互動。\n   - 選擇開關：『顯示 50MA 均量線』。\n4. 呈現與行為：\n   - 下方成交量圖表中，必須疊加一條平滑的半透明淺橙色折線代表『50 日平均成交量』。\n   - 當使用者將滑桿調高使單日成交量超越 50MA 時，在圖表上動態顯示標記為『放量突破』；反之標記為『乾涸區』。\n   - 介面與圖表標籤一律使用繁體中文，控制項位於頂部，採用與牛牛 APP 相似的乾淨深色主題樣式。"
          }
        }
        st.write(json_payload)

    # --- Minervini 趨勢條件檢查清單 (始終顯示於頂部摘要旁) ---
    criteria = [
        {"desc": "價格 > 150MA 與 200MA (價格在長線支撐之上)", "status": cur_p > last_daily['150MA'] and cur_p > last_daily['200MA']},
        {"desc": "150MA > 200MA (長線趨勢排列正確)", "status": last_daily['150MA'] > last_daily['200MA']},
        {"desc": "200MA 趨勢向上 (與一個月前相比)", "status": last_daily['200MA'] > daily_data['MA200_Past'].iloc[-1]},
        {"desc": "50MA > 150MA 與 200MA (中線動能加速)", "status": last_daily['50MA'] > last_daily['150MA'] and last_daily['50MA'] > last_daily['200MA']},
        {"desc": "
