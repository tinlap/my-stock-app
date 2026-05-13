import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 設定網頁標題與寬版顯示
st.set_page_config(page_title="專屬看盤系統 (自動篩選旗艦版)", layout="wide")
st.title("🦅 專屬專業看盤系統：富途牛牛旗艦版 + 自動篩選器")

# 建立兩大頂層功能分頁
main_tab1, main_tab2 = st.tabs(["📡 單股深度看盤 (牛牛風格)", "⚡ 市場自動篩選器 (Minervini 掃描)"])

# --- 核心數據抓取引擎 (支援快取) ---
@st.cache_data(ttl=3600)
def load_and_process_data(ticker, period="2y", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty and len(df) >= 50:
            df['50MA'] = df['Close'].rolling(window=50).mean()
            df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
            if len(df) >= 150:
                df['150MA'] = df['Close'].rolling(window=150).mean()
            else:
                df['150MA'] = None
            if len(df) >= 200:
                df['200MA'] = df['Close'].rolling(window=200).mean()
                df['MA200_Past'] = df['200MA'].shift(20)
            else:
                df['200MA'] = None
                df['MA200_Past'] = None
            return df
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 分頁一：單股深度看盤 (保留富途牛牛操作手感)
# ==========================================
with main_tab1:
    st.sidebar.header("📡 單股看盤設定")
    ticker_symbol = st.sidebar.text_input("輸入深度分析代號 (如: COHR, NVDA)", value="COHR").upper()
    
    daily_data = load_and_process_data(ticker_symbol, period="2y", interval="1d")

    if not daily_data.empty:
        cur_p = daily_data['Close'].iloc[-1]
        last_daily = daily_data.iloc[-1]
        
        last_year = daily_data.tail(252)
        hi52 = last_year['High'].max()
        lo52 = last_year['Low'].min()

        # Minervini 條件運算
        has_ma200 = pd.notna(last_daily['200MA'])
        c1 = (cur_p > last_daily['150MA'] and cur_p > last_daily['200MA']) if has_ma200 else False
        c2 = (last_daily['150MA'] > last_daily['200MA']) if has_ma200 else False
        c3 = (last_daily['200MA'] > last_daily['MA200_Past']) if (has_ma200 and pd.notna(last_daily['MA200_Past'])) else False
        c4 = (last_daily['50MA'] > last_daily['150MA'] and last_daily['50MA'] > last_daily['200MA']) if has_ma200 else False
        c5 = (cur_p > last_daily['50MA']) if pd.notna(last_daily['50MA']) else False
        c6 = cur_p > (lo52 * 1.30)
        c7 = cur_p > (hi52 * 0.75)

        criteria = [
            {"desc": "價格站上 150MA 與 200MA", "status": c1},
            {"desc": "150MA 高於 200MA (長線多頭)", "status": c2},
            {"desc": "200MA 趨勢向上", "status": c3},
            {"desc": "50MA 高於 150MA 與 200MA", "status": c4},
            {"desc": "價格站上 50MA", "status": c5},
            {"desc": "股價比 52 週最低點高出至少 30%", "status": c6},
            {"desc": "股價距離 52 週最高點在 25% 以內", "status": c7}
        ]
        pass_count = sum([c['status'] for c in criteria])

        # 頂部摘要
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新報價", f"${cur_p:.2f}")
        col2.metric("52週最高", f"${hi52:.2f}")
        col3.metric("52週最低", f"${lo52:.2f}")
        col4.metric("趨勢指標得分", f"{pass_count} / 7")

        with st.expander("📊 點此展開 Minervini 趨勢模板詳細健檢狀態"):
            col_list, col_res = st.columns([2, 1])
            with col_list:
                for c in criteria:
                    icon = "✅" if c['status'] else "❌"
                    st.write(f"{icon} {c['desc']}")
            with col_res:
                if pass_count == 7:
                    st.success(f"🔥 **{ticker_symbol} 完全符合 Stage 2 超級績效趨勢模板！**")
                else:
                    st.warning(f"目前結構偏弱，僅符合 {pass_count} 項條件。")

        # 繪圖區
        sub_d, sub_w, sub_m = st.tabs(["日K", "周K", "月K"])

        def render_futu_chart(ticker, period_str, interval_str):
            data = load_and_process_data(ticker, period=period_str, interval=interval_str)
            if not data.empty:
                df_plot = data.tail(252) if interval_str == "1d" else data
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])

                # K線
                fig.add_trace(go.Candlestick(
                    x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
                    low=df_plot['Low'], close=df_plot['Close'], name='K線',
                    increasing_line_color='#ff4a4a', decreasing_line_color='#00c873'
                ), row=1, col=1)

                # 均線
                if '50MA' in df_plot.columns and df_plot['50MA'].notna().any():
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['50MA'], name='50MA', line=dict(color='#2196F3', width=1.2)), row=1, col=1)
                if '150MA' in df_plot.columns and df_plot['150MA'].notna().any():
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['150MA'], name='150MA', line=dict(color='#FFC107', width=1.2)), row=1, col=1)
                if '200MA' in df_plot.columns and df_plot['200MA'].notna().any():
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['200MA'], name='200MA', line=dict(color='#F44336', width=1.5)), row=1, col=1)

                # 成交量
                vol_colors = ['#ff4a4a' if row['Open'] > row['Close'] else '#00c873' for _, row in df_plot.iterrows()]
                fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)

                if 'Vol_50MA' in df_plot.columns and df_plot['Vol_50MA'].notna().any():
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.65)', width=1.5)), row=2, col=1)

                fig.update_layout(
                    height=650, xaxis_rangeslider_visible=False, template="plotly_dark",
                    hovermode="x unified", hoverlabel=dict(bgcolor="#1e1e1e", font_size=13, font_color="#ffffff"),
                    margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig.update_xaxes(showgrid=True, gridcolor='#2a2a2a')
                fig.update_yaxes(showgrid=True, gridcolor='#2a2a2a')
                return fig
            return go.Figure()

        with sub_d: st.plotly_chart(render_futu_chart(ticker_symbol, "2y", "1d"), use_container_width=True)
        with sub_w: st.plotly_chart(render_futu_chart(ticker_symbol, "5y", "1wk"), use_container_width=True)
        with sub_m: st.plotly_chart(render_futu_chart(ticker_symbol, "15y", "1mo"), use_container_width=True)
    else:
        st.error("無法取得單股資料，請確認代號正確。")


# ==========================================
# 分頁二：自動化策略篩選器 (一鍵批量掃描)
# ==========================================
with main_tab2:
    st.subheader("⚡ 趨勢模板一鍵掃描機")
    st.write("系統支援批量抓取歷史數據並自動驗證所有條件。為了避免 API 過載斷線，請透過下方的代號池進行掃描設定：")

    # 預設放入高流動性科技成長板塊與你常看的標的
    default_pool = "COHR, NVDA, GOOG, SOFI, AAPL, MSFT, AMZN, TSLA, AMD, PLTR, META, NFLX, AVGO, QCOM, ARM, SMCI, MU, UBER, CRWD, MSTR, APP"
    
    tickers_input = st.text_area("自訂股票掃描池 (請以半形逗號分隔代號)：", value=default_pool, height=100)
    
    if st.button("🚀 立即開始掃描名單", type="primary"):
        # 清理字串產出代號清單
        ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        
        if not ticker_list:
            st.warning("請至少輸入一個股票代號！")
        else:
            scan_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_stocks = len(ticker_list)
            
            for i, t in enumerate(ticker_list):
                status_text.text(f"正在分析 ({i+1}/{total_stocks}): {t} ...")
                progress_bar.progress((i + 1) / total_stocks)
                
                df = load_and_process_data(t, period="2y", interval="1d")
                if df.empty or len(df) < 200:
                    continue
                    
                cur_p = df['Close'].iloc[-1]
                last_daily = df.iloc[-1]
                hi52 = df.tail(252)['High'].max()
                lo52 = df.tail(252)['Low'].min()
                
                has_ma200 = pd.notna(last_daily['200MA'])
                c1 = (cur_p > last_daily['150MA'] and cur_p > last_daily['200MA']) if has_ma200 else False
                c2 = (last_daily['150MA'] > last_daily['200MA']) if has_ma200 else False
                c3 = (last_daily['200MA'] > last_daily['MA200_Past']) if (has_ma200 and pd.notna(last_daily['MA200_Past'])) else False
                c4 = (last_daily['50MA'] > last_daily['150MA'] and last_daily['50MA'] > last_daily['200MA']) if has_ma200 else False
                c5 = (cur_p > last_daily['50MA']) if pd.notna(last_daily['50MA']) else False
                c6 = cur_p > (lo52 * 1.30)
                c7 = cur_p > (hi52 * 0.75)
                
                score = sum([c1, c2, c3, c4, c5, c6, c7])
                dist_to_high = ((cur_p - hi52) / hi52) * 100 # 距離最高點百分比
                
                scan_results.append({
                    "股票代號": t,
                    "最新收盤價": f"${cur_p:.2f}",
                    "健康總分": score,
                    " Stage 2 達標": "🔥 完全符合" if score == 7 else "否",
                    "距52週高點": f"{dist_to_high:.1f}%",
                    "50MA": f"${last_daily['50MA']:.2f}" if pd.notna(last_daily['50MA']) else "-",
                    "200MA": f"${last_daily['200MA']:.2f}" if has_ma200 else "-"
                })
            
            status_text.text("掃描完成！結果如下：")
            
            if scan_results:
                res_df = pd.DataFrame(scan_results)
                # 將完全符合的標的排在最上方，其次按總分排序
                res_df = res_df.sort_values(by=["健康總分"], ascending=False).reset_index(drop=True)
                
                # 顯示統計數據
                passed_stocks = res_df[res_df["健康總分"] == 7]["股票代號"].tolist()
                if passed_stocks:
                    st.success(f"🎯 恭喜！本次掃描共發現 **{len(passed_stocks)}** 檔完全符合 Mark Minervini 第二階段的標的： {', '.join(passed_stocks)}")
                else:
                    st.info("本次掃描未發現獲得滿分 7 分的標的，您可以從下方表格觀察得分 5~6 分、即將轉強的觀察名單。")
                
                # 使用 Streamlit 原生互動式資料表呈現
                st.dataframe(
                    res_df, 
                    use_container_width=True,
                    height=400,
                    column_config={
                        "健康總分": st.column_config.ProgressColumn("趨勢達標度", min_value=0, max_value=7, format="%d/7")
                    }
                )
            else:
                st.warning("無法抓取到有效數據，請確認代號正確性。")
