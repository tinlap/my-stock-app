import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="Minervini 專業趨勢監控台", layout="wide")
st.title("🦅 Mark Minervini 趨勢模板 V4 (含 50 日均量線)")

# 側邊欄設定
st.sidebar.header("設定參數")
ticker_symbol = st.sidebar.text_input("輸入股票代號", value="COHR").upper()
days = st.sidebar.slider("查看天數", min_value=100, max_value=500, value=250)

@st.cache_data(ttl=3600)
def load_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y")
    return df

df = load_data(ticker_symbol)

if not df.empty and len(df) > 200:
    # 1. 計算價格均線與成交量均線
    df['50MA'] = df['Close'].rolling(window=50).mean()
    df['150MA'] = df['Close'].rolling(window=150).mean()
    df['200MA'] = df['Close'].rolling(window=200).mean()
    df['Vol_50MA'] = df['Volume'].rolling(window=50).mean() # 新增：成交量 50 日均線
    
    ma200_past = df['200MA'].iloc[-20] 
    
    # 2. 取得最新關鍵數值
    cur_price = df['Close'].iloc[-1]
    cur_vol = df['Volume'].iloc[-1]
    vol_50ma = df['Vol_50MA'].iloc[-1]
    ma50 = df['50MA'].iloc[-1]
    ma150 = df['150MA'].iloc[-1]
    ma200 = df['200MA'].iloc[-1]
    
    hi_52w = df.tail(252)['High'].max()
    lo_52w = df.tail(252)['Low'].min()

    # 3. Minervini 趨勢條件判斷
    conditions = [
        (cur_price > ma150 and cur_price > ma200),
        (ma150 > ma200),
        (ma200 > ma200_past),
        (ma50 > ma150 and ma50 > ma200),
        (cur_price > ma50),
        (cur_price > lo_52w * 1.30),
        (cur_price > hi_52w * 0.75),
    ]
    
    pass_count = sum(conditions)
    is_stage_2 = all(conditions)

    # 頂部狀態欄
    cols = st.columns(5)
    cols[0].metric("最新收盤價", f"${cur_price:.2f}")
    cols[1].metric("52週最高", f"${hi_52w:.2f}")
    cols[2].metric("52週最低", f"${lo_52w:.2f}")
    cols[3].metric("最新成交量", f"{cur_vol:,}")
    cols[4].metric("篩選通過數", f"{pass_count} / 7")

    if is_stage_2:
        st.success(f"🔥 **{ticker_symbol} 符合完整 Stage 2 趨勢模板條件！**")
    else:
        st.warning(f"⚠️ **{ticker_symbol} 未完全符合，目前滿足 {pass_count} 項條件。**")

    # 4. 繪製圖表 (採用安全多行排版防止截斷)
    df_plot = df.tail(days)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, 
        vertical_spacing=0.03, 
        subplot_titles=(f'{ticker_symbol} 走勢', '成交量與 50MA 均量線'), 
        row_width=[0.2, 0.7]
    )

    # 上方主圖：K 線圖
    fig.add_trace(
        go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
            low=df_plot['Low'], close=df_plot['Close'], name='K線'
        ), 
        row=1, col=1
    )

    # 上方主圖：價格均線
    fig.add_trace(
        go.Scatter(
            x=df_plot.index, y=df_plot['50MA'], 
            name='50MA (藍)', line=dict(color='blue', width=1.5)
        ), 
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df_plot.index, y=df_plot['150MA'], 
            name='150MA (黃)', line=dict(color='yellow', width=1.5)
        ), 
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df_plot.index, y=df_plot['200MA'], 
            name='200MA (紅)', line=dict(color='red', width=2)
        ), 
        row=1, col=1
    )

    # 下方副圖：成交量柱狀圖
    colors = ['#ef5350' if row['Open'] > row['Close'] else '#26a69a' for _, row in df_plot.iterrows()]
    fig.add_trace(
        go.Bar(
            x=df_plot.index, y=df_plot['Volume'], 
            name='成交量', marker_color=colors
        ), 
        row=2, col=1
    )

    # 下方副圖：疊加 50 日平均成交量線 (淺橙色、半透明)
    fig.add_trace(
        go.Scatter(
            x=df_plot.index, y=df_plot['Vol_50MA'], 
            name='成交量 50MA', 
            line=dict(color='rgba(255, 165, 0, 0.6)', width=2), # 使用 rgba 設定透明度
            mode='lines'
        ), 
        row=2, col=1
    )

    fig.update_layout(
        height=800, 
        xaxis_rangeslider_visible=False, 
        template="plotly_dark",
        hovermode="x unified" # 讓游標移動時能同時顯示價格與成交量資訊
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("無法取得數據或數據量不足以計算 200MA。")
