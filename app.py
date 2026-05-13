import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="專屬看盤系統 (富途牛牛旗艦版)", layout="wide")
st.title("🦅 專屬專業看盤系統：富途牛牛旗艦版")

# --- 側邊欄：智能選股模組 ---
st.sidebar.header("設定標的")

# 預設的高品質觀察清單
default_watchlist = [
    "COHR", "NVDA", "GOOG", "SOFI", "O", 
    "TSLA", "AAPL", "MSFT", "AMZN", "META", 
    "AMD", "TSM", "PLTR", "SMCI", "ARM", 
    "SPY", "QQQ", "0700.HK", "0388.HK"
]

# 讓使用者選擇輸入模式
input_mode = st.sidebar.radio("選擇切換方式", ["📋 自選股快速選單", "✍️ 手動輸入其他代號"])

if input_mode == "📋 自選股快速選單":
    ticker_symbol = st.sidebar.selectbox("點擊選擇標的", default_watchlist)
else:
    ticker_symbol = st.sidebar.text_input("輸入全球股票代號 (美股直接打, 港股加.HK)", value="NFLX").upper()

# --- 底層數據抓取引擎 ---
@st.cache_data(ttl=3600)
def load_and_process_data(ticker, period, interval):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    
    if not df.empty:
        if len(df) >= 50:
            df['50MA'] = df['Close'].rolling(window=50).mean()
            df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
        else:
            df['50MA'], df['Vol_50MA'] = None, None
            
        if len(df) >= 150:
            df['150MA'] = df['Close'].rolling(window=150).mean()
        else:
            df['150MA'] = None
            
        if len(df) >= 200:
            df['200MA'] = df['Close'].rolling(window=200).mean()
            df['MA200_Past'] = df['200MA'].shift(20)
        else:
            df['200MA'], df['MA200_Past'] = None, None
            
        return df
    return pd.DataFrame()

daily_data = load_and_process_data(ticker_symbol, period="2y", interval="1d")

if not daily_data.empty:
    cur_p = daily_data['Close'].iloc[-1]
    last_daily = daily_data.iloc[-1]
    
    last_year = daily_data.tail(252)
    hi52 = last_year['High'].max()
    lo52 = last_year['Low'].min()

    # --- 核心邏輯運算 ---
    has_ma200 = pd.notna(last_daily['200MA'])
    
    c1 = (cur_p > last_daily['150MA'] and cur_p > last_daily['200MA']) if has_ma200 else False
    c2 = (last_daily['150MA'] > last_daily['200MA']) if has_ma200 else False
    c3 = (last_daily['200MA'] > last_daily['MA200_Past']) if (has_ma200 and pd.notna(last_daily['MA200_Past'])) else False
    c4 = (last_daily['50MA'] > last_daily['150MA'] and last_daily['50MA'] > last_daily['200MA']) if has_ma200 else False
    c5 = (cur_p > last_daily['50MA']) if pd.notna(last_daily['50MA']) else False
    c6 = cur_p > (lo52 * 1.30)
    c7 = cur_p > (hi52 * 0.75)

    criteria = [
        {"desc": "價格站上 150MA 與 200MA (長線支撐穩固)", "status": c1},
        {"desc": "150MA 高於 200MA (長線多頭排列)", "status": c2},
        {"desc": "200MA 趨勢向上 (長線動能回升)", "status": c3},
        {"desc": "50MA 高於 150MA 與 200MA (中線加速轉強)", "status": c4},
        {"desc": "價格站上 50MA (短線維持強勢結構)", "status": c5},
        {"desc": "股價比 52 週最低點高出至少 30% (脫離底部)", "status": c6},
        {"desc": "股價距離 52 週最高點在 25% 以內", "status": c7}
    ]
    
    pass_count = sum([c['status'] for c in criteria])

    # --- 頂部摘要 ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新報價", f"${cur_p:.2f}")
    col2.metric("52週最高", f"${hi52:.2f}")
    col3.metric("52週最低", f"${lo52:.2f}")
    col4.metric("趨勢指標得分", f"{pass_count} / 7")

    with st.expander("📊 點此展開 Minervini 趨勢模板詳細健檢狀態", expanded=False):
        col_list, col_res = st.columns([2, 1])
        with col_list:
            for c in criteria:
                icon = "✅" if c['status'] else "❌"
                st.write(f"{icon} {c['desc']}")
        with col_res:
            if pass_count == 7:
                st.success(f"🔥 **{ticker_symbol} 完全符合 Stage 2 超級績效趨勢模板！**")
            elif pass_count >= 5:
                st.info(f"蓄勢待發：已滿足 {pass_count} 項條件。")
            else:
                st.warning(f"目前結構偏弱或處於調整，僅符合 {pass_count} 項條件。")

    # --- 繪圖區 ---
    st.subheader("📡 專業看盤主控台")
    tab_d, tab_w, tab_m = st.tabs(["日K", "周K", "月K"])

    def render_futu_chart(ticker, period_str, interval_str):
        data = load_and_process_data(ticker, period=period_str, interval=interval_str)
        if not data.empty:
            df_plot = data.tail(252) if interval_str == "1d" else data
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])

            fig.add_trace(go.Candlestick(
                x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
                low=df_plot['Low'], close=df_plot['Close'], name='K線',
                increasing_line_color='#ff4a4a', decreasing_line_color='#00c873'
            ), row=1, col=1)

            if '50MA' in df_plot.columns and df_plot['50MA'].notna().any():
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50MA', line=dict(color='#2196F3', width=1.2)), row=1, col=1)
            if '150MA' in df_plot.columns and df_plot['150MA'].notna().any():
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], name='150MA', line=dict(color='#FFC107', width=1.2)), row=1, col=1)
            if '200MA' in df_plot.columns and df_plot['200MA'].notna().any():
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], name='200MA', line=dict(color='#F44336', width=1.5)), row=1, col=1)

            vol_colors = ['#ff4a4a' if row['Open'] > row['Close'] else '#00c873' for _, row in df_plot.iterrows()]
            fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)

            if 'Vol_50MA' in df_plot.columns and df_plot['Vol_50MA'].notna().any():
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.65)', width=1.5)), row=2, col=1)

            fig.update_layout(
                height=680, xaxis_rangeslider_visible=False, template="plotly_dark",
                hovermode="x unified", hoverlabel=dict(bgcolor="#1e1e1e", font_size=13, font_color="#ffffff"),
                margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig.update_xaxes(showgrid=True, gridcolor='#2a2a2a')
            fig.update_yaxes(showgrid=True, gridcolor='#2a2a2a')
            return fig
        return go.Figure()

    with tab_d:
        st.plotly_chart(render_futu_chart(ticker_symbol, "2y", "1d"), use_container_width=True)
    with tab_w:
        st.plotly_chart(render_futu_chart(ticker_symbol, "5y", "1wk"), use_container_width=True)
    with tab_m:
        st.plotly_chart(render_futu_chart(ticker_symbol, "15y", "1mo"), use_container_width=True)

else:
    st.error("無法取得該代號的市場資料，請確認代號輸入正確。")
