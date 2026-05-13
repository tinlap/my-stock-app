import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# ==========================================
# 1. 系統設定與品牌命名
# ==========================================
APP_NAME = "鷹眼 (EagleEye) 智能趨勢選股系統"
VERSION = "V19"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION} (量價財報雙修版)")

# --- 側邊欄控制中心 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

# 強制重整功能：遇到數據卡住或 API 沒反應時點擊
if st.sidebar.button("♻️ 強制清空緩存並重整"):
    st.cache_data.clear()
    st.rerun()

# 預設的高質量美股池 (內建常用標的)
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# ==========================================
# 2. 核心數據引擎 (具備高穩定性與容錯機制)
# ==========================================

@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    """從 GitHub CDN 或 Wikipedia 抓取標普 500 名單"""
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
            table = pd.read_html(response.text)
            return [str(t).replace('.', '-') for t in table[0]['Symbol'].tolist()]
        except:
            return TECH_GIANTS + GROWTH_STARS

@st.cache_data(ttl=3600)
def load_spy_benchmark():
    """計算 SPY 標普 500 指數半年報酬率作為 RS 基準"""
    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1d")
        if not spy.empty and len(spy) > 126:
            return (spy['Close'].iloc[-1] / spy['Close'].iloc[-126]) - 1
    except: pass
    return 0.05 

SPY_6M_REF = load_spy_benchmark()

@st.cache_data(ttl=3600)
def get_stock_comprehensive_data(ticker):
    """抓取單檔股票的技術面與基本面數據"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 200: return pd.DataFrame(), {}
        
        # 抓取財報數據 (雙重備援邏輯)
        info = {}
        try:
            info = stock.info
        except: pass
        
        # 技術指標計算
        df['50MA'] = df['Close'].rolling(window=50).mean()
        df['150MA'] = df['Close'].rolling(window=150).mean()
        df['200MA'] = df['Close'].rolling(window=200).mean()
        df['MA200_Past'] = df['200MA'].shift(20)
        df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
        
        # 財報成長率提取
        eps_g = info.get('earningsQuarterlyGrowth') or info.get('quarterlyEarningsGrowth')
        rev_g = info.get('revenueGrowth') or info.get('quarterlyRevenueGrowth')
        
        fund_data = {
            "eps": eps_g * 100 if eps_g else None,
            "rev": rev_g * 100 if rev_g else None,
            "name": info.get('shortName', ticker)
        }
        return df, fund_data
    except:
        return pd.DataFrame(), {}

def evaluate_minervini(df, fund_data):
    """執行全套 Mark Minervini 篩選邏輯"""
    if df.empty or len(df) < 200: return 0, False, {}
    
    cur_p = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    hi52 = float(df.tail(252)['High'].max())
    lo52 = float(df.tail(252)['Low'].min())
    
    # 7 大技術準則
    c1 = cur_p > last['150MA'] and cur_p > last['200MA']
    c2 = last['150MA'] > last['200MA']
    c3 = last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False
    c4 = last['50MA'] > last['150MA'] and last['50MA'] > last['200MA']
    c5 = cur_p > last['50MA']
    c6 = cur_p > lo52 * 1.3
    c7 = cur_p > hi52 * 0.75
    
    tech_score = sum([c1, c2, c3, c4, c5, c6, c7])
    
    # 相對強度與量縮
    ret_6m = (cur_p / df['Close'].iloc[-126]) - 1 if len(df) > 126 else 0
    vcp_dry = last['Volume'] < (last['Vol_50MA'] * 0.75) if pd.notna(last['Vol_50MA']) else False
    
    return tech_score, (tech_score == 7), {
        "price": cur_p, "hi52": hi52, "lo52": lo52,
        "rs_outperform": ret_6m > SPY_6M_REF,
        "vcp_dry": vcp_dry,
        "eps": fund_data.get('eps'), "rev": fund_data.get('rev')
    }

# ==========================================
# 3. 頁面模式：全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼全市場掃描雷達")
    st.caption("自動掃描標的池，找出技術面、籌碼面、基本面三位一體的超級領頭羊。")
    
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        pool_choice = st.radio("選擇掃描板塊：", ["🌟 美股熱門精選 (22檔)", "🇺🇸 標普 500 全部成份股", "✍️ 自訂代號掃描"])
    with c_p2:
        min_score = st.slider("技術面最低門檻：", 4, 7, 6)
        filter_rs = st.checkbox("👑 必須跑贏標普 500 大盤", value=True)
        filter_fund = st.checkbox("📈 必須具備正向財報成長", value=False)

    if st.button("🏁 啟動全方位雷達掃描", type="primary"):
        sp500_list = fetch_sp500_tickers()
        if "熱門" in pool_choice: scan_list = TECH_GIANTS + GROWTH_STARS
        elif "標普" in pool_choice: scan_list = sp500_list
        else:
            custom_input = st.text_area("請輸入代號 (逗號隔開)", "COHR, NVDA, GOOG, PLTR")
            scan_list = [t.strip().upper() for t in custom_input.split(",") if t.strip()]

        results = []
        prog = st.progress(0)
        status = st.empty()

        for i, ticker in enumerate(scan_list):
            status.text(f"掃描中 ({i+1}/{len(scan_list)}): {ticker}")
            df, fund = get_stock_comprehensive_data(ticker)
            if not df.empty:
                score, is_pass, m = evaluate_minervini(df, fund)
                
                # 過濾邏輯
                rs_cond = m['rs_outperform'] if filter_rs else True
                growth_cond = ((m['eps'] and m['eps'] > 0) or (m['rev'] and m['rev'] > 0)) if filter_growth else True
                
                if score >= min_score and rs_cond and growth_cond:
                    results.append({
                        "代號": ticker, "得分": f"{score}/7", "狀態": "🔥 符合" if is_pass else "轉強中",
                        "價格": f"${m['price']:.2f}", "跑贏大盤": "✅" if m['rs_outperform'] else "❌",
                        "VCP量縮": "💧" if m['vcp_dry'] else "-",
                        "EPS成長": f"{m['eps']:.1f}%" if m['eps'] else "N/A",
                        "營收成長": f"{m['rev']:.1f}%" if m['rev'] else "N/A"
                    })
            prog.progress((i + 1) / len(scan_list))
        
        status.success(f"完成！共發現 {len(results)} 檔達標強勢股。")
        if results: st.table(pd.DataFrame(results))

# ==========================================
# 4. 頁面模式：個股深度分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    ticker = st.sidebar.text_input("🎯 輸入美股代號查看詳情", value="NVDA").upper()
    
    df, fund = get_stock_comprehensive_data(ticker)
    if not df.empty:
        score, is_pass, m = evaluate_minervini(df, fund)
        
        # 頂部數據儀表板
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前價格", f"${m['price']:.2f}")
        c2.metric("趨勢綜合評分", f"{score} / 7")
        c3.metric("季度 EPS 成長", f"{m['eps']:.1f}%" if m['eps'] else "無數據")
        c4.metric("季度營收成長", f"{m['rev']:.1f}%" if m['rev'] else "無數據")
        
        # 常駐健檢清單
        st.markdown("---")
        st.subheader("📋 超級績效技術面健檢")
        l_col, r_col = st.columns([2, 1])
        with l_col:
            last = df.iloc[-1]
            st.write(f"{'✅' if m['price'] > last['150MA'] and m['price'] > last['200MA'] else '❌'} 價格高於 150MA 與 200MA")
            st.write(f"{'✅' if last['150MA'] > last['200MA'] else '❌'} 150MA 高於 200MA (多頭排列)")
            st.write(f"{'✅' if last['50MA'] > last['150MA'] else '❌'} 50MA 高於 150MA")
            st.write(f"{'✅' if m['rs_outperform'] else '❌'} 相對強度：跑贏標普 500 大盤")
            st.write(f"{'✅' if m['vcp_dry'] else '❌'} 籌碼狀態：末端成交量呈乾涸縮小 (VCP)")
        with r_col:
            if is_pass: st.success("💎 該股完全符合第二階段上升模板！")
            else: st.info(f"目前滿足 {score} 項技術條件。")

        # 專業 K 線區
        tabs = st.tabs(["日K 旗艦圖", "周K 波段圖", "月K 長線圖"])
        
        def draw_futu_style(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            # K線
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            # 均線
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA', line=dict(color='#2196F3', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA', line=dict(color='#FFC107', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA', line=dict(color='#F44336', width=1.5)), row=1, col=1)
            # 成交量
            v_cols = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=v_cols), row=2, col=1)
            # 50均量線
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.6)', width=1.5)), row=2, col=1)
            
            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
            return fig

        with tabs[0]: st.plotly_chart(draw_futu_style(df), use_container_width=True)
        with tabs[1]:
            w_df = yf.Ticker(ticker).history(period="5y", interval="1wk")
            if not w_df.empty:
                w_df['50MA'] = w_df['Close'].rolling(50).mean()
                w_df['150MA'] = w_df['Close'].rolling(150).mean()
                w_df['200MA'] = w_df['Close'].rolling(200).mean()
                w_df['Vol_50MA'] = w_df['Volume'].rolling(50).mean()
                st.plotly_chart(draw_futu_style(w_df), use_container_width=True)
        with tabs[2]:
            m_df = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not m_df.empty:
                m_df['50MA'] = m_df['Close'].rolling(50).mean()
                m_df['150MA'] = m_df['Close'].rolling(150).mean()
                m_df['200MA'] = m_df['Close'].rolling(200).mean()
                m_df['Vol_50MA'] = m_df['Volume'].rolling(50).mean()
                st.plotly_chart(draw_futu_style(m_df), use_container_width=True)
    else:
        st.error("無法抓取數據，請確認代號或強制刷新緩存。")
