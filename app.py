import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="Minervini 專業監控 V3", layout="wide")
st.title("🦅 Mark Minervini 趨勢模板 V3 (詳細檢查清單)")

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
    # 1. 計算均線
    df['50MA'] = df['Close'].rolling(window=50).mean()
    df['150MA'] = df['Close'].rolling(window=150).mean()
    df['200MA'] = df['Close'].rolling(window=200).mean()
    ma200_past = df['200MA'].iloc[-20] 
    
    # 2. 取得數值
    cur_p = df['Close'].iloc[-1]
    m50 = df['50MA'].iloc[-1]
    m150 = df['150MA'].iloc[-1]
    m200 = df['200MA'].iloc[-1]
    h52 = df.tail(252)['High'].max()
    l52 = df.tail(252)['Low'].min()

    # 3. 定義 7 大條件及其描述
    criteria = [
        {"desc": "價格需高於 150MA 與 200MA", "status": cur_p > m150 and cur_p > m200},
        {"desc": "150MA 需高於 200MA", "status": m150 > m200},
        {"desc": "200MA 趨勢需向上 (與一個月前相比)", "status": m200 > ma200_past},
        {"desc": "50MA 需高於 150MA 與 200MA", "status": m50 > m150 and m50 > m200},
        {"desc": "價格需高於 50MA", "status": cur_p > m50},
        {"desc": "需比 52 週最低點高出 30%", "status": cur_p > l52 * 1.30},
        {"desc": "距離 52 週最高點需在 25% 以內", "status": cur_p > h52 * 0.75}
    ]
    
    pass_count = sum([c['status'] for c in criteria])

    # 顯示儀表板
    col_main, col_check = st.columns([2, 1])

    with col_check:
        st.subheader("📋 趨勢模板檢查清單")
        st.write(f"**總分：{pass_count} / 7**")
        for c in criteria:
            icon = "✅" if c['status'] else "❌"
            st.write(f"{icon} {c['desc']}")

    with col_main:
        # 繪製圖表 (簡化繪圖邏輯以防截斷)
        df_plot = df.tail(days)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.7])
        
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50MA (藍)', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], name='150MA (黃)', line=dict(color='yellow')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], name='200MA (紅)', line=dict(color='red')), row=1, col=1)
        
        # 成交量
        vol_colors = ['#ef5350' if r['Open'] > r['Close'] else '#26a69a' for _, r in df_plot.iterrows()]
        fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
        
        fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

else:
    st.error("數據不足或無法抓取代號，請檢查輸入是否正確。")
