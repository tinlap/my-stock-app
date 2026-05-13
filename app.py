import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

# 設定網頁標題與寬版顯示
st.set_page_config(page_title="專屬看盤系統 (智能選股旗艦版)", layout="wide")
st.title("🦅 專屬專業看盤系統：智能選股掃描旗艦版")

# --- 側邊欄：功能分頁與標的設定 ---
st.sidebar.header("系統導覽")
page_mode = st.sidebar.radio("選擇功能頁面", ["📊 個股深度看盤", "🔍 智能趨勢選股器 (Screener)"])

# 內建精選美股與熱門成長股池 (約40檔高流動性標的，隨時可擴充)
STOCK_UNIVERSE = [
    "NVDA", "COHR", "GOOG", "AAPL", "MSFT", "AMZN", "META", "TSLA", "AMD", "TSM",
    "PLTR", "SMCI", "ARM", "SOFI", "O", "NFLX", "AVGO", "QCOM", "MU", "INTC",
    "CRWD", "NOW", "UBER", "CRM", "ADBE", "PYPL", "SQ", "SHOP", "SPOT", "HOOD",
    "PFE", "DIS", "WMT", "COST", "JPM", "V", "MA", "SPY", "QQQ"
]

@st.cache_data(ttl=3600)
def load_and_process_data(ticker, period="2y", interval="1d"):
    """抓取單檔股票數據並計算各項均線與指標"""
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
    except Exception:
        pass
    return pd.DataFrame()

def evaluate_minervini_criteria(df):
    """計算是否符合 Mark Minervini 7大技術面條件"""
    if df.empty or len(df) < 200:
        return 0, False, {}
    
    cur_p = df['Close'].iloc[-1]
    last_row = df.iloc[-1]
    
    # 52週高低點 (取最後252天)
    last_year = df.tail(252)
    hi52 = last_year['High'].max()
    lo52 = last_year['Low'].min()
    
    has_ma200 = pd.notna(last_row['200MA'])
    
    c1 = (cur_p > last_row['150MA'] and cur_p > last_row['200MA']) if has_ma200 else False
    c2 = (last_row['150MA'] > last_row['200MA']) if has_ma200 else False
    c3 = (last_row['200MA'] > last_row['MA200_Past']) if (has_ma200 and pd.notna(last_row['MA200_Past'])) else False
    c4 = (last_row['50MA'] > last_row['150MA'] and last_row['50MA'] > last_row['200MA']) if has_ma200 else False
    c5 = (cur_p > last_row['50MA']) if pd.notna(last_row['50MA']) else False
    c6 = cur_p > (lo52 * 1.30)
    c7 = cur_p > (hi52 * 0.75)
    
    criteria_results = {
        "c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6, "c7": c7
    }
    pass_count = sum(criteria_results.values())
    return pass_count, (pass_count == 7), {
        "price": cur_p, "hi52": hi52, "lo52": lo52, "50ma": last_row['50MA'],
        "150ma": last_row['150MA'], "200ma": last_row['200MA']
    }

# ==========================================
# 頁面一：個股深度看盤 (保留常駐清單與專業圖表)
# ==========================================
if page_mode == "📊 個股深度看盤":
    st.sidebar.markdown("---")
    st.sidebar.header("個股設定")
    input_mode = st.sidebar.radio("輸入模式", ["📋 快速選擇", "✍️ 自訂輸入"])
    
    if input_mode == "📋 快速選擇":
        ticker_symbol = st.sidebar.selectbox("選擇股票", STOCK_UNIVERSE)
    else:
        ticker_symbol = st.sidebar.text_input("輸入代號 (如 NFLX, 0700.HK)", value="COHR").upper()

    daily_data = load_and_process_data(ticker_symbol, "2y", "1d")
    
    if not daily_data.empty:
        pass_count, is_stage2, metrics = evaluate_minervini_criteria(daily_data)
        
        # 頂部數據
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新報價", f"${metrics['price']:.2f}")
        c2.metric("52週最高", f"${metrics['hi52']:.2f}")
        c3.metric("52週最低", f"${metrics['lo52']:.2f}")
        c4.metric("趨勢指標得分", f"{pass_count} / 7")
        
        # 健檢清單直接常駐顯示
        st.markdown("---")
        st.subheader("📋 第二階段 (Stage 2) 趨勢模板健檢清單")
        
        c_list, c_res = st.columns([2, 1])
        with c_list:
            st.write(f"{'✅' if metrics['price'] > metrics['150ma'] and metrics['price'] > metrics['200ma'] else '❌'} 價格站上 150MA 與 200MA")
            st.write(f"{'✅' if metrics['150ma'] > metrics['200ma'] else '❌'} 150MA 高於 200MA (長線多頭)")
            st.write(f"{'✅' if metrics['200ma'] > daily_data['MA200_Past'].iloc[-1] else '❌'} 200MA 趨勢向上")
            st.write(f"{'✅' if metrics['50ma'] > metrics['150ma'] and metrics['50ma'] > metrics['200ma'] else '❌'} 50MA 高於 150MA 與 200MA")
            st.write(f"{'✅' if metrics['price'] > metrics['50ma'] else '❌'} 價格站上 50MA")
            st.write(f"{'✅' if metrics['price'] > metrics['lo52'] * 1.3 else '❌'} 比 52 週最低點高出至少 30%")
            st.write(f"{'✅' if metrics['price'] > metrics['hi52'] * 0.75 else '❌'} 距離 52 週最高點在 25% 以內")
            
        with c_res:
            if is_stage2:
                st.success(f"🔥 **{ticker_symbol} 完全符合 Stage 2 超級績效趨勢！**")
            elif pass_count >= 5:
                st.info(f"蓄勢待發：已滿足 {pass_count} 項條件。")
            else:
                st.warning(f"目前結構偏弱或處於調整期，僅符合 {pass_count} 項條件。")
        st.markdown("---")
        
        # 繪圖區
        st.subheader("📡 專業看盤主控台")
        tab_d, tab_w, tab_m = st.tabs(["日K", "周K", "月K"])
        
        def render_futu_chart(df_data, interval_str):
            df_plot = df_data.tail(252) if interval_str == "1d" else df_data
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

        with tab_d:
            st.plotly_chart(render_futu_chart(daily_data, "1d"), use_container_width=True)
        with tab_w:
            w_data = load_and_process_data(ticker_symbol, "5y", "1wk")
            if not w_data.empty:
                st.plotly_chart(render_futu_chart(w_data, "1wk"), use_container_width=True)
        with tab_m:
            m_data = load_and_process_data(ticker_symbol, "15y", "1mo")
            if not m_data.empty:
                st.plotly_chart(render_futu_chart(m_data, "1mo"), use_container_width=True)
    else:
        st.error("無法取得資料，請確認代號是否正確。")

# ==========================================
# 頁面二：智能趨勢選股器 (自動批量掃描 Screener)
# ==========================================
elif page_mode == "🔍 智能趨勢選股器 (Screener)":
    st.subheader("🦅 Mark Minervini 趨勢自動化選股掃描器")
    st.write("系統將自動連線抓取下方指定的股票池數據，並光速過濾出技術面達標的強勢個股。")
    
    # 讓使用者可以動態編輯或添加掃描名單
    custom_pool_str = st.text_area("自訂掃描股票池 (以半形逗號分隔，可自行隨意貼上更多代號)", value=", ".join(STOCK_UNIVERSE))
    scan_pool = [t.strip().upper() for t in custom_pool_str.split(",") if t.strip()]
    
    min_score = st.slider("過濾門檻：最低需符合幾項條件", min_value=4, max_value=7, value=6)
    
    if st.button("🚀 立即開始全自動掃描", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(scan_pool):
            status_text.text(f"正在連線分析標的 ({i+1}/{len(scan_pool)}): {ticker} ...")
            df = load_and_process_data(ticker, period="2y", interval="1d")
            
            if not df.empty:
                score, is_pass, m = evaluate_minervini_criteria(df)
                if score >= min_score:
                    results.append({
                        "股票代號": ticker,
                        "健檢總分": f"{score} / 7",
                        "完全符合": "🔥 是" if is_pass else "蓄勢中",
                        "最新收盤價": f"${m['price']:.2f}",
                        "距52週高點": f"{(m['price'] - m['hi52']) / m['hi52'] * 100:.1f}%",
                        "距52週低點": f"{(m['price'] - m['lo52']) / m['lo52'] * 100:.1f}%",
                        "50MA": f"${m['50ma']:.2f}" if pd.notna(m['50ma']) else "-",
                        "200MA": f"${m['200ma']:.2f}" if pd.notna(m['200ma']) else "-"
                    })
            progress_bar.progress((i + 1) / len(scan_pool))
            
        status_text.success(f"掃描完畢！共掃描 {len(scan_pool)} 檔標的，為你篩選出 {len(results)} 檔達標強勢股。")
        
        if results:
            df_res = pd.DataFrame(results)
            st.dataframe(
                df_res, 
                use_container_width=True,
                column_config={
                    "完全符合": st.column_config.TextColumn("Stage 2 狀態"),
                    "健檢總分": st.column_config.TextColumn("得分門檻")
                }
            )
            st.info("💡 **高效率看盤秘訣**：記下表格中挑出的優質代號，點擊左邊欄切換回 **「📊 個股深度看盤」**，就能立刻對照它的 K 線圖與透明橙色均量線進行精確進場點的覆盤！")
        else:
            st.warning("目前股票池中沒有達到該分數門檻的標的，建議稍微調降過濾標準，或擴充文字框內的股票代號。")
