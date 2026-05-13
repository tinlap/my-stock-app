import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Minervini 趨勢監控台", layout="wide")
st.title("🦅 專屬看盤系統：Minervini 趨勢與技術分析")

# 側邊欄設定
st.sidebar.header("設定參數")
ticker_symbol = st.sidebar.text_input("輸入股票代號 (例如: GOOG, NVDA, COHR)", value="COHR").upper()
days = st.sidebar.slider("K線圖顯示天數", min_value=90, max_value=500, value=250)

@st.cache_data(ttl=3600)
def load_data(ticker):
    stock = yf.Ticker(ticker)
    # 抓取足夠天數以計算 200MA
    df = stock.history(period="2y")
    return df, stock.info

df, info = load_data(ticker_symbol)

if not df.empty and len(df) > 200:
    # 計算均線
    df['50MA'] = df['Close'].rolling(window=50).mean()
    df['150MA'] = df['Close'].rolling(window=150).mean()
    df['200MA'] = df['Close'].rolling(window=200).mean()
    
    # 最新數據
    current_close = df['Close'].iloc[-1]
    current_50ma = df['50MA'].iloc[-1]
    current_150ma = df['150MA'].iloc[-1]
    current_200ma = df['200MA'].iloc[-1]
    
    # 52週高低點
    last_52_weeks = df.tail(252)
    high_52w = last_52_weeks['High'].max()
    low_52w = last_52_weeks['Low'].min()
    
    # Minervini 趨勢模板條件判斷
    cond1 = current_close > current_150ma and current_close > current_200ma
    cond2 = current_150ma > current_200ma
    cond3 = current_close > current_50ma
    cond4 = current_close > (low_52w * 1.3) # 至少比52週低點高30%
    cond5 = current_close > (high_52w * 0.75) # 距離52週高點在25%以內
    
    is_stage_2 = cond1 and cond2 and cond3 and cond4 and cond5

    # 頂部儀表板
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新收盤價", f"${current_close:.2f}")
    col2.metric("50日均線", f"${current_50ma:.2f}")
    col3.metric("150日均線", f"${current_150ma:.2f}")
    col4.metric("200日均線", f"${current_200ma:.2f}")
    
    # 狀態提示
    if is_stage_2:
        st.success(f"🔥 **{ticker_symbol} 目前完全符合 Minervini 趨勢模板條件！(處於 Stage 2 上升趨勢)**")
    else:
        st.warning(f"📊 **{ticker_symbol} 目前未完全滿足趨勢模板，請注意均線排列或距高低點位置。**")

    # 截取使用者指定天數繪圖
    df_plot = df.tail(days)
    
    fig = go.Figure()
    # K線
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
        low=df_plot['Low'], close=df_plot['Close'], name='K線',
        increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
    ))
    # 加入均線
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], mode='lines', name='50MA', line=dict(color='magenta', width=1.5)))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], mode='lines', name='150MA', line=dict(color='orange', width=1.5)))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], mode='lines', name='200MA', line=dict(color='blue', width=2)))

    fig.update_layout(
        height=650, 
        xaxis_rangeslider_visible=False,
        title=f"{ticker_symbol} 走勢與成交量分析",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("資料不足！計算 200MA 需要至少 200 天的交易日數據，請嘗試其他上市較久的標的。")
