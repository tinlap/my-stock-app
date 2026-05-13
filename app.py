import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# ==========================================
# 系統設定與品牌命名
# ==========================================
APP_NAME = "鷹眼 (EagleEye) 智能趨勢選股系統"
VERSION = "V16"

st.set_page_config(page_title=f"{APP_NAME} {VERSION}", layout="wide")
st.title(f"🦅 {APP_NAME} {VERSION} (技術與基本面雙引擎旗艦版)")

# --- 側邊欄：智能導覽 ---
st.sidebar.header("🕹️ 系統控制中心")
page_mode = st.sidebar.radio("切換功能模式", ["🔍 全自動選股掃描器 (Screener)", "📊 個股深度分析 (Chart)"])

# 預設的高質量美股觀察池
TECH_GIANTS = ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AMD", "TSM", "AVGO", "NFLX"]
GROWTH_STARS = ["COHR", "PLTR", "SMCI", "ARM", "SOFI", "UBER", "CRWD", "NOW", "SHOP", "SQ", "SPOT"]

# --- 核心數據引擎：GitHub CDN 讀取 S&P 500 ---
@st.cache_data(ttl=86400)
def fetch_sp500_tickers():
    try:
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(csv_url)
        return [str(t).replace('.', '-') for t in df['Symbol'].tolist()]
    except Exception:
        return TECH_GIANTS + GROWTH_STARS

# --- 抓取大盤 SPY 作為相對強度 (RS) 基準 ---
@st.cache_data(ttl=3600)
def load_spy_benchmark():
    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1d")
        if not spy.empty and len(spy) > 120:
            # 計算半年 (約126個交易日) 的累積報酬率
            return (spy['Close'].iloc[-1] / spy['Close'].iloc[-126]) - 1
    except: pass
    return 0.05 # 預設基準

SPY_6M_RETURN = load_spy_benchmark()

# --- 核心個股深度抓取 (包含技術面與基本面 info) ---
@st.cache_data(ttl=3600)
def load_stock_complete_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        info = stock.info if hasattr(stock, 'info') else {}
        
        if not df.empty and len(df) >= 200:
            df['50MA'] = df['Close'].rolling(window=50).mean()
            df['150MA'] = df['Close'].rolling(window=150).mean()
            df['200MA'] = df['Close'].rolling(window=200).mean()
            df['MA200_Past'] = df['200MA'].shift(20)
            df['Vol_50MA'] = df['Volume'].rolling(window=50).mean()
            
            # 安全提取基本面數據
            eps_growth = info.get('earningsQuarterlyGrowth', info.get('quarterlyEarningsGrowth', np.nan))
            rev_growth = info.get('revenueGrowth', np.nan)
            
            return df, {
                "eps_growth": eps_growth * 100 if pd.notna(eps_growth) else None,
                "rev_growth": rev_growth * 100 if pd.notna(rev_growth) else None
            }
    except: pass
    return pd.DataFrame(), {}

def run_ultimate_logic(df, fund_data):
    if df.empty or len(df) < 200: return 0, False, {}
    cur_p = float(df['Close'].iloc[-1])
    last = df.iloc[-1]
    hi52 = float(df.tail(252)['High'].max())
    lo52 = float(df.tail(252)['Low'].min())
    
    # 計算近半年累積報酬率
    stock_6m_return = (cur_p / df['Close'].iloc[-126]) - 1 if len(df) > 126 else 0
    
    # 1. 純技術面 7 大準則
    c1 = cur_p > last['150MA'] and cur_p > last['200MA']
    c2 = last['150MA'] > last['200MA']
    c3 = last['200MA'] > last['MA200_Past'] if pd.notna(last['MA200_Past']) else False
    c4 = last['50MA'] > last['150MA'] and last['50MA'] > last['200MA']
    c5 = cur_p > last['50MA']
    c6 = cur_p > lo52 * 1.3
    c7 = cur_p > hi52 * 0.75
    tech_score = sum([c1, c2, c3, c4, c5, c6, c7])
    
    # 2. 進階靈魂指標：相對強度跑贏大盤與 VCP 量縮偵測
    outperform_spy = stock_6m_return > SPY_6M_RETURN
    vcp_dry_up = last['Volume'] < (last['Vol_50MA'] * 0.75) if pd.notna(last['Vol_50MA']) else False
    
    return tech_score, (tech_score == 7), {
        "price": cur_p, "hi52": hi52, "lo52": lo52,
        "stock_6m_ret": stock_6m_return * 100,
        "outperform_spy": outperform_spy,
        "vcp_dry_up": vcp_dry_up,
        "eps_growth": fund_data.get('eps_growth'),
        "rev_growth": fund_data.get('rev_growth')
    }

# ==========================================
# 頁面一：🔍 全自動選股掃描器 (Screener)
# ==========================================
if page_mode == "🔍 全自動選股掃描器 (Screener)":
    st.subheader("🚀 鷹眼終極全市場掃描雷達 (量價與財報過濾)")
    st.write("同時分析技術面趨勢排列、大盤相對強度 (RS) 以及最新季度營收與獲利爆發力。")
    
    col_sel1, col_sel2, col_sel3 = st.columns([1.5, 1, 1])
    with col_sel1:
        pool_choice = st.radio(
            "請選擇自動掃描範圍：",
            [
                "🌟 美股核心科技巨頭 (11檔)",
                "🔥 高成長強勢股清單 (11檔)",
                "🇺🇸 標普 500 前 50 檔熱門權值股",
                "🇺🇸 標普 500 前 100 檔熱門權值股",
                "🇺🇸 標普 500 全成份股掃描 (約500檔，需時較長)",
                "✍️ 自訂代號手動掃描"
            ]
        )
    with col_sel2:
        target_score = st.slider("技術面最低門檻得分：", 4, 7, 6)
    with col_sel3:
        filter_spy = st.checkbox("👑 必須嚴格跑贏標普500大盤", value=True)
        filter_growth = st.checkbox("📈 必須具備正向營收或獲利成長", value=False)

    if st.button("🏁 啟動全自動多維度掃描", type="primary"):
        sp500_all = fetch_sp500_tickers()
        if pool_choice == "🌟 美股核心科技巨頭 (11檔)": scan_list = TECH_GIANTS
        elif pool_choice == "🔥 高成長強勢股清單 (11檔)": scan_list = GROWTH_STARS
        elif "前 50 檔" in pool_choice: scan_list = sp500_all[:50]
        elif "前 100 檔" in pool_choice: scan_list = sp500_all[:100]
        elif "全成份股" in pool_choice: scan_list = sp500_all
        else:
            custom_str = st.text_area("自訂掃描代號 (逗號隔開)", "COHR, NVDA, PLTR, TSM")
            scan_list = [t.strip().upper() for t in custom_str.split(",") if t.strip()]

        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(scan_list):
            status.text(f"正在多維度掃描 ({i+1}/{len(scan_list)}): {t}")
            df, fund_data = load_stock_complete_data(t)
            if not df.empty:
                score, is_pass, m = run_ultimate_logic(df, fund_data)
                
                # 執行進階條件判斷
                spy_cond = m['outperform_spy'] if filter_spy else True
                eps_g = m['eps_growth']
                rev_g = m['rev_growth']
                has_growth = (eps_g is not None and eps_g > 0) or (rev_g is not None and rev_g > 0)
                growth_cond = has_growth if filter_growth else True
                
                if score >= target_score and spy_cond and growth_cond:
                    results.append({
                        "代號": t, 
                        "技術評分": f"{score}/7", 
                        "Stage 2 狀態": "🔥 完美符合" if is_pass else "轉強中",
                        "最新價": f"${m['price']:.2f}",
                        "跑贏大盤": "👑 是" if m['outperform_spy'] else "否",
                        "VCP量縮": "💧 乾涸" if m['vcp_dry_up'] else "正常",
                        "季盈餘成長": f"{eps_g:.1f}%" if eps_g is not None else "-",
                        "季營收成長": f"{rev_g:.1f}%" if rev_g is not None else "-"
                    })
            progress.progress((i + 1) / len(scan_list))
        
        status.success(f"掃描大功告成！在 {len(scan_list)} 檔標的內為您篩選出 {len(results)} 檔超級潛力股。")
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("目前範圍內無標的同時滿足設定的技術與基本面過濾條件。")

# ==========================================
# 頁面二：📊 個股深度分析 (Chart)
# ==========================================
else:
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 個股深度搜索")
    input_type = st.sidebar.radio("選股方式", ["下拉快速切換", "手動輸入代號"])
    
    combined_list = TECH_GIANTS + GROWTH_STARS
    ticker = st.sidebar.selectbox("選取標的", combined_list) if input_type == "下拉快速切換" else st.sidebar.text_input("輸入美股代號", value="COHR").upper()
    
    df_daily, fund_data = load_stock_complete_data(ticker)
    if not df_daily.empty:
        score, is_pass, m = run_ultimate_logic(df_daily, fund_data)
        
        # 頂部全視角儀表板 (新增基本面與RS展示)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("當前價格", f"${m['price']:.2f}")
        c2.metric("趨勢技術評分", f"{score} / 7")
        c3.metric("近半年報酬率", f"{m['stock_6m_ret']:.1f}%", f"{m['stock_6m_ret'] - (SPY_6M_RETURN*100):.1f}% vs 大盤")
        
        eps_str = f"{m['eps_growth']:.1f}%" if m['eps_growth'] is not None else "無資料"
        c4.metric("最新季EPS成長", eps_str)
        rev_str = f"{m['rev_growth']:.1f}%" if m['rev_growth'] is not None else "無資料"
        c5.metric("最新季營收成長", rev_str)
        c6.metric("末端成交量狀態", "💧 VCP 乾涸點" if m['vcp_dry_up'] else "流動性充足")
        
        # 常駐綜合健檢清單
        st.markdown("---")
        st.subheader("📋 超級績效全方位健檢清單 (技術面 ＋ 籌碼面 ＋ 基本面)")
        l_col, r_col = st.columns([2, 1])
        with l_col:
            last = df_daily.iloc[-1]
            st.write(f"{'✅' if m['price'] > last['150MA'] and m['price'] > last['200MA'] else '❌'} 價格站上長線 150MA 與 200MA")
            st.write(f"{'✅' if last['150MA'] > last['200MA'] else '❌'} 長線均線呈現多頭排列 (150MA > 200MA)")
            st.write(f"{'✅' if last['200MA'] > df_daily['MA200_Past'].iloc[-1] else '❌'} 200 日均線趨勢明確向上")
            st.write(f"{'✅' if last['50MA'] > last['150MA'] and last['50MA'] > last['200MA'] else '❌'} 50MA 位於最上方 (中長線動能加速)")
            st.write(f"{'✅' if m['price'] > last['50MA'] else '❌'} 股價守住短線 50 日防守線")
            st.write(f"{'✅' if m['price'] > m['lo52']*1.3 else '❌'} 股價顯著脫離 52 週最低點至少 30%")
            st.write(f"{'✅' if m['price'] > m['hi52']*0.75 else '❌'} 距離 52 週最高點在 25% 以內 (頂部強勢區)")
            st.markdown("💡 **V16 進階靈魂指標**")
            st.write(f"{'👑 領跑大盤' if m['outperform_spy'] else '⚠️ 落後大盤'} 個股近半年走勢強於標普 500 指數 (相對強度達標)")
            st.write(f"{'💧 完美收縮' if m['vcp_dry_up'] else '📊 正常換手'} 最新單日成交量顯著縮小至 50 日均量的 75% 以下 (符合 VCP 右側特徵)")
        with r_col:
            if is_pass and m['outperform_spy']:
                st.success(f"💎 **{ticker} 具備超級飆股特質！技術面全過且相對強度超越大盤，請密切留意右側突破點。**")
            else:
                st.info(f"技術面滿足 {score}/7 項條件。可透過上方財報動能確認是否有實質獲利支撐。")
        st.markdown("---")
        
        # 專業看盤區
        t1, t2, t3 = st.tabs(["日K 旗艦走勢", "周K 波段走勢", "月K 長線走勢"])
        def draw_chart(data):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.25, 0.75])
            df_p = data.tail(252) if len(data) > 252 else data
            fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['50MA'], name='50MA (藍)', line=dict(color='blue', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['150MA'], name='150MA (黃)', line=dict(color='yellow', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['200MA'], name='200MA (紅)', line=dict(color='red', width=1.5)), row=1, col=1)
            vol_colors = ['#ff4a4a' if r['Open'] > r['Close'] else '#00c873' for _, r in df_p.iterrows()]
            fig.add_trace(go.Bar(x=df_p.index, y=df_p['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Vol_50MA'], name='50均量', line=dict(color='rgba(255, 165, 0, 0.6)')), row=2, col=1)
            fig.update_layout(height=680, xaxis_rangeslider_visible=False, template="plotly_dark", hovermode="x unified")
            fig.update_xaxes(showgrid=True, gridcolor='#2a2a2a')
            fig.update_yaxes(showgrid=True, gridcolor='#2a2a2a')
            return fig

        with t1: st.plotly_chart(draw_chart(df_daily), use_container_width=True)
        with t2:
            w_data = yf.Ticker(ticker).history(period="5y", interval="1wk")
            if not w_data.empty:
                w_data['50MA'] = w_data['Close'].rolling(50).mean()
                w_data['150MA'] = w_data['Close'].rolling(150).mean()
                w_data['200MA'] = w_data['Close'].rolling(200).mean()
                w_data['Vol_50MA'] = w_data['Volume'].rolling(50).mean()
                st.plotly_chart(draw_chart(w_data), use_container_width=True)
        with t3:
            m_data = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not m_data.empty:
                m_data['50MA'] = m_data['Close'].rolling(50).mean()
                m_data['150MA'] = m_data['Close'].rolling(150).mean()
                m_data['200MA'] = m_data['Close'].rolling(200).mean()
                m_data['Vol_50MA'] = m_data['Volume'].rolling(50).mean()
                st.plotly_chart(draw_chart(m_data), use_container_width=True)
    else:
        st.error("查無資料，請確認代號是否正確。")
