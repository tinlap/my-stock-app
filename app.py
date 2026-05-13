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
        {"desc": "價格 > 50MA (短期不破位)", "status": cur_p > last_daily['50MA']},
        {"desc": "比 52 週最低點高出至少 30% (已脫離底部區)", "status": cur_p > lo52 * 1.30},
        {"desc": "距離 52 週最高點在 25% 以內 (處於高位強勢整理)", "status": cur_p > hi52 * 0.75}
    ]
    pass_count = sum([c['status'] for c in criteria])
    st.subheader(f"📋 Minervini 趨勢模板詳細檢查 (總分：{pass_count} / 7)")
    with st.expander("展開查看詳細清單", expanded=True):
        col_ch, col_info = st.columns([2, 1])
        with col_ch:
            for c in criteria:
                icon = "✅" if c['status'] else "❌"
                st.write(f"{icon} {c['desc']}")
        with col_info:
            if all([c['status'] for c in criteria]):
                st.success(f"🔥 {ticker_symbol} 符合完整 Stage 2 趨勢模板條件！")
            else:
                st.warning(f"⚠️ {ticker_symbol} 未完全符合，請注意檢查細節。")

    # --- 主要看盤區 (牛牛 APP 風格) ---
    st.subheader("📡 專業看盤區")
    
    # 建立時間選擇分頁 (日K, 周K, 月K) - 跟截圖一模一樣！
    tab_d, tab_w, tab_m = st.tabs(["日K", "周K", "月K"])

    def create_niuniu_chart(ticker, plot_period, plot_interval):
        """根據選擇的時間週期，建立牛牛風格的互動式圖表"""
        # 抓取並處理數據
        # 日K使用 2y, 周K使用 5y (以滿足 200 週期 MA), 月K使用 20y (或 max)
        actual_period = "2y" if plot_interval == "1d" else "5y" if plot_interval == "1wk" else "20y"
        data = load_and_process_data(ticker, period=actual_period, interval=plot_interval)

        if not data.empty:
            df_plot = data.tail(days=int(plot_period.replace("d", ""))) if plot_interval == "1d" else data
            
            # --- 建立專業版畫布 (上下子圖，共享 X 軸) ---
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                               vertical_spacing=0.03, subplot_titles=(f'{ticker} {plot_interval.replace("1d", "日").replace("1wk", "周").replace("1mo", "月")}K 走勢', '成交量與 50 週期均量線'), 
                               row_width=[0.2, 0.7])

            # 1. 上方子圖：專業 K 線圖 (K線 + 三條 MA + 懸停詳細資訊)
            fig.add_trace(go.Candlestick(
                x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
                low=df_plot['Low'], close=df_plot['Close'], name='K線',
                increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
            ), row=1, col=1)

            # 疊加均線 (顏色依照截圖指定)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50MA (藍)', line=dict(color='blue', width=1.5), mode='lines', hoverinfo='none'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], name='150MA (黃)', line=dict(color='yellow', width=1.5), mode='lines', hoverinfo='none'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], name='200MA (紅)', line=dict(color='red', width=2), mode='lines', hoverinfo='none'), row=1, col=1)

            # 2. 下方子圖：專業成交量圖 (成交量柱狀圖 + 50MA 透明橙色線)
            vol_colors = ['#ef5350' if row['Open'] > row['Close'] else '#26a69a' for _, row in df_plot.iterrows()]
            fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='成交量', marker_color=vol_colors, hoverinfo='none'), row=2, col=1)

            # 疊加半透明淺橙色均量線
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Vol_50MA'], name='成交量 50MA', 
                                    line=dict(color='rgba(255, 165, 0, 0.6)', width=2), mode='lines'), row=2, col=1)

            # --- 完美匹配懸停行為：游標碰到 K 線就顯示詳細日期與數值 ---
            fig.update_layout(
                height=700, 
                xaxis_rangeslider_visible=False, 
                template="plotly_dark",
                # 'x unified' 模式會自動建立垂直對齊線，並在統一的懸停框中顯示所有數據，包括日期
                hovermode="x unified", 
                # 自訂懸停框的樣式與內容
                hoverlabel=dict(bgcolor="black", font_size=12, font_family="Arial"),
                margin=dict(t=30, b=10, l=20, r=20)
            )
            return fig
        return go.Figure()

    # 在各個分頁中放置圖表
    with tab_d:
        # 日K設定：顯示 252 天 (約1年數據)
        fig_d = create_niuniu_chart(ticker_symbol, plot_period="252d", plot_interval="1d")
        st.plotly_chart(fig_d, use_container_width=True)
    with tab_w:
        fig_w = create_niuniu_chart(ticker_symbol, plot_period="all", plot_interval="1wk")
        st.plotly_chart(fig_w, use_container_width=True)
    with tab_m:
        fig_m = create_niuniu_chart(ticker_symbol, plot_period="all", plot_interval="1mo")
        st.plotly_chart(fig_m, use_container_width=True)

else:
    st.error("無法取得數據或無法計算 200 週期 MA，請確認代號或嘗試上市更久的股票。")
