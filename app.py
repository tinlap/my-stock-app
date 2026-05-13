import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="Minervini 專業趨勢監控台", layout="wide")
st.title("🦅 Mark Minervini 趨勢模板 V2 (含成交量)")

# 側邊欄設定
st.sidebar.header("設定參數")
ticker_symbol = st.sidebar.text_input("輸入股票代號", value="COHR").upper()
days = st.sidebar.slider("查看天數", min_value=100, max_value=500, value=250)

@st.cache_data(ttl=3600)
def load_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y")
    return df, stock.info

df, info = load_data(ticker_symbol)

if not df.empty and len(df) > 200:
    # 1. 計算均線
    df['50MA'] = df['Close'].rolling(window=50).mean()
    df['150MA'] = df['Close'].rolling(window=150).mean()
    df['200MA'] = df['Close'].rolling(window=200).mean()
    # 用於判斷 200MA 是否向上 (一個月前)
    ma200_past = df['200MA'].iloc[-20] 
    
    # 2. 取得關鍵數值
    cur_price = df['Close'].iloc[-1]
    ma50 = df['50MA'].iloc[-1]
    ma150 = df['150MA'].iloc[-1]
    ma200 = df['200MA'].iloc[-1]
    
    hi_52w = df.tail(252)['High'].max()
    lo_52w = df.tail(252)['Low'].min()

    # 3. Minervini 8 大硬指標判斷
    conditions = [
        (cur_price > ma150 and cur_price > ma200),           # 1. 價格在 150 & 200MA 之上
        (ma150 > ma200),                                     # 2. 150MA 在 200MA 之上
        (ma200 > ma200_past),                                # 3. 200MA 至少向上一個月
        (ma50 > ma150 and ma50 > ma200),                    # 4. 50MA 在 150 & 200MA 之上
        (cur_price > ma50),                                  # 5. 價格在 50MA 之上
        (cur_price > lo_52w * 1.30),                        # 6. 比 52 週低點高 30%
        (cur_price > hi_52w * 0.75),                        # 7. 距離 52 週高點 25% 以內
    ]
    
    pass_count = sum(conditions)
    is_stage_2 = all(conditions)

    # 頂部狀態欄
    cols = st.columns(4)
    cols[0].metric("最新價", f"${cur_price:.2f}")
    cols[1].metric("52週最高", f"${hi_52w:.2f}")
    cols[2].metric("52週最低", f"${lo_52w:.2f}")
    cols[3].metric("篩選通過數", f"{pass_count} / 7")

    if is_stage_2:
        st.success(f"🔥 {ticker_symbol} 符合完整 Stage 2 趨勢模板條件！")
    else:
        st.warning(f"⚠️ {ticker_symbol} 未完全符合，目前滿足 {pass_count} 項條件。")

    # 4. 繪製圖表 (子圖：上方 K 線，下方成交量)
    df_plot = df.tail(days)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.03, subplot_titles=(f'{ticker_symbol} 走勢', '成交量'), 
                       row_width=[0.2, 0.7])

    # K 線圖
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
        low=df_plot['Low'], close=df_plot['Close'], name='K線'
    ), row=1, col=1)

    # 加入均線 (指定顏色)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50
