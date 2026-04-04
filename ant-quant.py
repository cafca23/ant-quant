import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import google.generativeai as genai
import re

st.set_page_config(page_title="앤트리치 퀀트 터미널", layout="wide", page_icon="📈", initial_sidebar_state="expanded")

# --- Custom Premium CSS ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 700 !important; color: #e6edf3; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.85rem !important; letter-spacing: 0.05em; }
    .banner { padding: 1.5rem; border-radius: 8px; text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .buy-banner { background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%); color: white; border: 1px solid #1565c0; } 
    .hold-banner { background: linear-gradient(135deg, #052e16 0%, #166534 100%); color: white; border: 1px solid #15803d; }
    .sell-banner { background: linear-gradient(135deg, #450a0a 0%, #991b1b 100%); color: white; border: 1px solid #b91c1c; } 
    .banner h2 { margin: 0; padding: 0; font-size: 2.2rem; text-shadow: 0 2px 4px rgba(0,0,0,0.4); }
    .banner p { margin: 8px 0 0 0; font-size: 1.15rem; opacity: 0.95; font-weight: 500;}
    .checklist-box { background-color: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
    .badge { padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.9rem; margin-bottom: 10px; display: inline-block; }
    .badge-growth { background-color: rgba(162, 28, 175, 0.2); color: #e879f9; border: 1px solid #c026d3; }
    .badge-value { background-color: rgba(3, 105, 161, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
    .peer-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.95rem; }
    .peer-table th { background-color: #161b22; color: #8b949e; padding: 12px 8px; text-align: right; border-bottom: 2px solid #30363d; font-weight: 600; }
    .peer-table th:first-child { text-align: left; }
    .peer-table td { padding: 10px 8px; text-align: right; border-bottom: 1px solid #21262d; color: #e6edf3; }
    .peer-table td:first-child { text-align: left; font-weight: bold; }
    .peer-main-row { background-color: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; }
    .peer-median-row { background-color: #21262d; font-weight: bold; color: #8b949e; border-top: 2px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# 💡 실시간 거시경제 데이터
@st.cache_data(ttl=3600, show_spinner=False)
def get_macro_data():
    try: usdkrw = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
    except: usdkrw = 1350.0
    try: tnx = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    except: tnx = 4.2  
    return float(usdkrw), float(tnx)

# 💡 AI 기반 동종 업계 경쟁사 자동 탐색기
@st.cache_data(ttl=86400, show_spinner="AI가 해당 산업의 최적 경쟁사를 탐색 중입니다... 🕵️‍♂️")
def get_dynamic_peers(ticker, name, sector):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.1})
        prompt = f"Find 3 major US publicly traded competitors for {name} ({ticker}) in the {sector} sector. Return ONLY the 3 ticker symbols separated by commas (e.g., CVX, XOM, COP). No markdown, no explanation."
        res = model.generate_content(prompt)
        clean_res = res.text.strip().replace(" ", "").replace("\n", "")
        if len(clean_res) > 20: return ""
        return clean_res
    except: return ""

@st.cache_data(ttl=3600, show_spinner="경쟁사 멀티플 데이터를 수집 중입니다...")
def get_peers_data(ticker, peer_str):
    peer_list = [p.strip().upper() for p in peer_str.split(",") if p.strip()]
    if ticker not in peer_list:
        peer_list = [ticker] + peer_list
        
    data = []
    for p in peer_list:
        try:
            info = yf.Ticker(p).info
            data.append({
                "Ticker": p,
                "Price": info.get("currentPrice", np.nan),
                "Fwd P/E": info.get("forwardPE", np.nan),
                "EV/EBITDA": info.get("enterpriseToEbitda", np.nan),
                "P/S": info.get("priceToSalesTrailing12Months", np.nan),
                "EV/Rev": info.get("enterpriseToRevenue", np.nan)
            })
        except: pass
    return pd.DataFrame(data)

@st.cache_data(ttl=3600, show_spinner="티커 재무 데이터를 분석하고 있습니다...")
def get_stock_market_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="2y")
    hist_10y = stock.history(period="10y", interval="1mo")
    hist_daily_5y = stock.history(period="5y", interval="1d")
    hist_weekly = hist_daily_5y.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna() if not hist_daily_5y.empty else pd.DataFrame()
    return info, hist, hist_10y, hist_weekly

ex_rate, risk_free_rate = get_macro_data()

PEER_MAP = {
    "ORCL": "MSFT, CRM, SAP", "AAPL": "MSFT, GOOGL, DELL", "MSFT": "AAPL, GOOGL, ORCL",
    "TSLA": "TM, F, GM", "NVDA": "AMD, INTC, TSM", "GOOGL": "META, MSFT, AMZN",
    "AMZN": "WMT, TGT, GOOGL", "META": "GOOGL, SNAP, PINS", "AMD": "NVDA, INTC, QCOM"
}

with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    ticker_input = st.text_input("종목 티커 입력 (예: ORCL, OXY, KO)", value="ORCL")
    
    currency_opt = st.radio("💱 표시 통화", ["$ 달러", "₩ 원화"], horizontal=True)
    is_krw = currency_opt == "₩ 원화"
    
    st.divider()
    
    st.markdown("### 🤝 동종 업계 (Peer) 설정")
    default_peers = "MSFT, GOOGL, AAPL" 
    
    default_g = 15.0
    sgr_caption = "💡 AI 추천 성장률: 정보 없음 (기본값 15.0% 적용)"
    
    if ticker_input:
        ticker_for_sidebar = ticker_input.upper()
        try:
            info_sb, _, _, _ = get_stock_market_data(ticker_for_sidebar)
            
            if ticker_for_sidebar in PEER_MAP:
                default_peers = PEER_MAP[ticker_for_sidebar]
            else:
                company_name = info_sb.get('shortName', ticker_for_sidebar)
                sector = info_sb.get('sector', '')
                ai_peers = get_dynamic_peers(ticker_for_sidebar, company_name, sector)
                if ai_peers: 
                    default_peers = ai_peers
            
            # 💡 [핵심 완벽 패치] 가치주 성장률 뻥튀기 원천 차단
            roe_sb = info_sb.get('returnOnEquity', 0)
            payout_sb = info_sb.get('payoutRatio', 0) if info_sb.get('payoutRatio') else 0
            sector_sb = info_sb.get('sector', '')
            
            is_value_stock = False
            # 1. 굴뚝/전통 산업이거나 2. 배당을 40% 이상 준다면 무조건 가치주로 컷오프
            value_sectors = ["Consumer Defensive", "Utilities", "Energy", "Real Estate", "Financial Services", "Basic Materials", "Industrials"]
            if any(v_sec in sector_sb for v_sec in value_sectors) or payout_sb >= 0.40:
                is_value_stock = True
            
            if roe_sb is not None and roe_sb > 0:
                if is_value_stock:
                    # 가치/배당주는 ROE 함정에 속지 않고 5.0%로 보수적 강제 세팅
                    default_g = 5.0
                    sgr_caption = f"💡 전통 가치주 보수적 세팅: {default_g}% (강제 고정)"
                else:
                    sgr = max(5.0, min(roe_sb * (1 - payout_sb) * 100, 50.0))
                    default_g = float(round(sgr, 1))
                    sgr_caption = f"💡 자동 추천 성장률(SGR 기반): {default_g}%"
        except: pass

    peer_input = st.text_input("경쟁사 티커 (쉼표로 구분)", value=default_peers, help="AI가 자동으로 찾아낸 경쟁사입니다. 직접 수정하셔도 됩니다.")

    if 'last_ticker' not in st.session_state or st.session_state.last_ticker != ticker_input:
        st.session_state.g_slider = default_g
        st.session_state.last_ticker = ticker_input
        
    st.divider()
    
    st.markdown("### 🌐 거시경제(매크로) 연동")
    st.info(f"실시간 美 10년물 국채 금리: **{risk_free_rate:.2f}%**")
    discount_rate = round(risk_free_rate + 5.0, 1) 
    st.caption(f"💡 AI 자동 세팅 할인율: **{discount_rate}%** (국채 금리 + 시장리스크 5%)")
    
    st.divider()
        
    def set_g(val): st.session_state.g_slider = val

    g = st.slider("예상 성장률 (g) %", min_value=0.0, max_value=50.0, step=0.5, key="g_slider", help="기업의 향후 5~10년 기대 성장률")
    c1, c2, c3, c4 = st.columns(4)
    c1.button("10", on_click=set_g, args=(10.0,), width="stretch")
    c2.button("20", on_click=set_g, args=(20.0,), width="stretch")
    c3.button("30", on_click=set_g, args=(30.0,), width="stretch")
    c4.button("5", on_click=set_g, args=(5.0,), width="stretch")
    st.button("🔄 SGR 기반 (AI추천)", on_click=set_g, args=(default_g,), width="stretch")
    st.caption(sgr_caption)

def fmt_price(val):
    if pd.isna(val) or val == "N/A" or val is None: return "N/A"
    if is_krw: return f"₩{val * ex_rate:,.0f}"
    return f"${val:,.2f}"

def fmt_multi(val):
    if pd.isna(val) or val == "N/A" or val is None: return "-"
    return f"{val:.2f}배"

# --- 메인 로직 ---
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.markdown("<h1 style='margin-bottom: 0; font-size: 2.0rem;'>📈 앤트리치 퀀트 터미널</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8b949e; font-size: 1.05rem; margin-top: 5px;'>월스트리트 DCF + 상대가치(Multiples) 하이브리드 엔진</p>", unsafe_allow_html=True)

if ticker_input:
    ticker = ticker_input.upper()
    try:
        info, hist, hist_10y, hist_weekly = get_stock_market_data(ticker)
        
        if hist.empty or len(hist) < 200:
            st.error("데이터가 부족하거나 티커가 올바르지 않습니다.")
        else:
            hist['SMA50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA200'] = hist['Close'].rolling(window=200).mean()
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))

            current_price = info.get('currentPrice', hist['Close'].iloc[-1])
            sma50_val = hist['SMA50'].iloc[-1]
            sma200_val = hist['SMA200'].iloc[-1]
            rsi_val = hist['RSI'].iloc[-1]
            
            eps = info.get('trailingEps', info.get('forwardEps', 0))
            pbr = info.get('priceToBook', 'N/A')
            roe = info.get('returnOnEquity', None)
            debt_to_equity = info.get('debtToEquity', None)
            peg_ratio = info.get('pegRatio', None)
            fcf = info.get('freeCashflow', None)
            payout_ratio = info.get('payoutRatio', 0) if info.get('payoutRatio') else 0
            shares = info.get('sharesOutstanding', None)
            sector = info.get('sector', '')
            
            ev_ebitda = info.get('enterpriseToEbitda', None)
            ps_ratio = info.get('priceToSalesTrailing12Months', None)
            ev_revenue = info.get('enterpriseToRevenue', None)
            forward_pe = info.get('forwardPE', None)
            
            # 💡 [핵심 완벽 패치] 메인 화면 적정주가 모델 스위치도 동일하게 적용
            is_main_value_stock = False
            value_sectors = ["Consumer Defensive", "Utilities", "Energy", "Real Estate", "Financial Services", "Basic Materials", "Industrials"]
            if any(v_sec in sector for v_sec in value_sectors) or payout_ratio >= 0.40:
                is_main_value_stock = True
            
            graham_value = "N/A"
            if eps is not None and eps > 0: graham_value = eps * (8.5 + 2 * g)
                
            dcf_value = "N/A"
            if fcf is not None and fcf > 0 and shares is not None:
                wacc = discount_rate / 100
                g_dec = g / 100
                term_g = 0.025 
                pv_fcf = sum([(fcf * ((1 + g_dec) ** i)) / ((1 + wacc) ** i) for i in range(1, 6)])
                tv = (fcf * ((1 + g_dec) ** 5) * (1 + term_g)) / max((wacc - term_g), 0.001)
                pv_tv = tv / ((1 + wacc) ** 5)
                dcf_value = (pv_fcf + pv_tv) / shares
                
            if not is_main_value_stock and dcf_value != "N/A":
                final_fair_value = dcf_value
                model_used = "DCF(현금흐름할인) 모델"
                badge_html = "<div class='badge badge-growth'>🚀 AI 판독: 테크/성장주 트랙 자동 적용 중</div>"
            else:
                final_fair_value = graham_value
                model_used = "벤저민 그레이엄 모델"
                badge_html = "<div class='badge badge-value'>🏛️ AI 판독: 전통 가치/배당주 트랙 자동 적용 중</div>"
                
            margin_of_safety = "N/A"
            if final_fair_value != "N/A":
                margin_of_safety = ((final_fair_value - current_price) / abs(final_fair_value)) * 100

            hist_1y = hist.tail(252).copy()
            high_1y = hist_1y['High'].max()
            low_1y = hist_1y['Low'].min()
            drawdown = ((current_price - high_1y) / high_1y) * 100
            mdd = (hist_1y['Close'] / hist_1y['Close'].cummax() - 1.0).min() * 100
            
            df_wk = pd.DataFrame()
            if not hist_weekly.empty:
                df_wk = hist_weekly.copy()
                df_wk['MA10'] = df_wk['Close'].rolling(window=10).mean()
                df_wk['MA20'] = df_wk['Close'].rolling(window=20).mean()
                df_wk['MA60'] = df_wk['Close'].rolling(window=60).mean()
                df_wk['MA120'] = df_wk['Close'].rolling(window=120).mean()
                df_wk['Prev_Close'] = df_wk['Close'].shift(1)
                tr1 = df_wk['High'] - df_wk['Low']
                tr2 = (df_wk['High'] - df_wk['Prev_Close']).abs()
                tr3 = (df_wk['Low'] - df_wk['Prev_Close']).abs()
                df_wk['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                df_wk['ATR_22'] = df_wk['TR'].ewm(alpha=1/22, adjust=False).mean()
                df_wk['High_22'] = df_wk['High'].rolling(window=22).max()
                df_wk['Calc_Stop'] = df_wk['High_22'] - (df_wk['ATR_22'] * 3.0)
                
                atr_stop = np.zeros(len(df_wk))
                atr_stop[:] = np.nan
                calc_val = df_wk['Calc_Stop'].values
                close_val = df_wk['Close'].values
                for i in range(1, len(df_wk)):
                    if np.isnan(calc_val[i]): continue
                    prev_c, prev_s, cur_c = close_val[i-1], atr_stop[i-1], calc_val[i]
                    if np.isnan(prev_s): atr_stop[i] = cur_c
                    elif prev_c > prev_s: atr_stop[i] = max(cur_c, prev_s)
                    else: atr_stop[i] = cur_c
                df_wk['ATR_Stop'] = atr_stop
                
                ma_stack = df_wk[['MA10', 'MA20', 'MA60']]
                df_wk['Converged'] = ((ma_stack.max(axis=1) - ma_stack.min(axis=1)) / ma_stack.min(axis=1)).round(4) <= 0.0700
                df_wk['Signal_Main'] = (df_wk['Converged'] & (df_wk['Close'] > df_wk['MA20']) & (df_wk['Close'] > df_wk['MA60']) & (df_wk['MA60'] >= df_wk['MA120']) & (df_wk['Close'] > df_wk['ATR_Stop']))
                df_wk['Signal_Main'] = df_wk['Signal_Main'] & (~df_wk['Signal_Main'].shift(1).fillna(False))
                df_wk['Signal_Reentry'] = ((df_wk['Close'] > df_wk['MA60']) & ((df_wk['Prev_Close'] <= df_wk['MA10'].shift(1)) & (df_wk['Close'] > df_wk['MA10'])) & (df_wk['Close'] > df_wk['Open']) & (df_wk['MA20'] > df_wk['MA20'].shift(1)) & (df_wk['Close'] > df_wk['ATR_Stop']) & (~df_wk['Signal_Main']))
                df_wk['Signal_Sell'] = (df_wk['Prev_Close'] >= df_wk['ATR_Stop'].shift(1)) & (df_wk['Close'] < df_wk['ATR_Stop'])

            score = 0; checklist = []
            if margin_of_safety != "N/A":
                if margin_of_safety > 20: score += 2; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+2"})
                elif margin_of_safety > 0: score += 1; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+1"})
                else: checklist.append({"status": "fail", "category": "가치", "desc": "고평가 상태 (안전마진 부족)", "score": "0"})
            else: checklist.append({"status": "info", "category": "가치", "desc": "적정 주가 산출 불가", "score": "-"})
                
            if roe is not None and roe > 0.15: score += 2; checklist.append({"status": "pass", "category": "수익성", "desc": f"ROE 15% 초과 ({roe*100:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "수익성", "desc": f"ROE 15% 미달", "score": "0"})
                
            if debt_to_equity is not None and debt_to_equity < 100: score += 2; checklist.append({"status": "pass", "category": "건전성", "desc": f"안정적인 부채비율 ({debt_to_equity:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "건전성", "desc": f"부채비율 높음", "score": "0"})
                
            if pd.notna(sma50_val) and pd.notna(sma200_val):
                if current_price > sma50_val and sma50_val > sma200_val: score += 3; checklist.append({"status": "pass", "category": "일봉 추세", "desc": "정배열 상승", "score": "+3"})
                elif current_price > sma50_val and sma50_val <= sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "바닥 반등 시작", "score": "+1"})
                elif current_price <= sma50_val and current_price > sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "장기 상승장 속 조정 (눌림목)", "score": "+1"})
                else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "역배열 하락세", "score": "0"})
            else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "추세 판독 불가", "score": "0"})
                
            if pd.notna(rsi_val) and rsi_val < 70: score += 1; checklist.append({"status": "pass", "category": "단기 수급", "desc": f"RSI 과열 아님 ({rsi_val:.1f})", "score": "+1"})
            else: checklist.append({"status": "fail", "category": "단기 수급", "desc": "RSI 단기 과열", "score": "0"})

            if score >= 8: judgment = "🌟 강력 매수 (Strong Buy)"; banner_class = "buy-banner"; prog_color = "#1976d2"
            elif score >= 5: judgment = "🟢 분할 매수 / 관망 (Accumulate/Hold)"; banner_class = "hold-banner"; prog_color = "#166534"
            else: judgment = "🔴 매도 / 주의 (Sell/Warning)"; banner_class = "sell-banner"; prog_color = "#b91c1c"
            
            st.markdown(f"""
<div class="banner {banner_class}">
    <h2>{info.get('shortName', ticker)} ({ticker})</h2>
    <p>퀀트 평가 등급: <b style="font-size:1.3rem;">{judgment}</b> &nbsp;|&nbsp; 스코어 : <b>{score} 점</b> </p>
</div>
""", unsafe_allow_html=True)
            
            items_html = "".join([f'''<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; margin-bottom: 8px; background-color: #161b22; border-radius: 6px; border-left: 4px solid {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; border: 1px solid #30363d;">
    <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
        <span style="font-size: 1.1rem;">{'✅' if item["status"] == 'pass' else ('❌' if item["status"] == 'fail' else '💡')}</span>
        <span style="color: {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; font-weight: bold; font-size: 0.8rem; min-width: 50px; text-align: center;">{item["category"]}</span>
        <span style="color: #c9d1d9; font-size: 0.95rem;">{item["desc"]}</span>
    </div>
    <div style="font-weight: bold; color: {'#3fb950' if item["status"] == 'pass' else ('#f85149' if item["status"] == 'fail' else '#d29922')}; font-size: 1.05rem;">{item["score"]}점</div>
</div>''' for item in checklist])
            
            st.markdown(f"""
<div style="display: flex; gap: 20px; align-items: stretch; margin-bottom: 20px; flex-wrap: wrap;">
    <div class='checklist-box' style='flex: 1 1 300px; text-align:center; display: flex; flex-direction: column; justify-content: center;'>
        <h3 style='margin:0 0 10px 0; color:#8b949e;'>TOTAL SCORE</h3>
        <h1 style='font-size: 5rem; margin:10px 0; color:{prog_color};'>{score}<span style='font-size: 2.5rem; color:#8b949e;'> / 10</span></h1>
    </div>
    <div class='checklist-box' style='flex: 1.8 1 500px; justify-content: flex-start;'>
        <h3 style='margin:0 0 15px 0; color:#8b949e;'>평가 내용</h3>{items_html}
    </div>
</div>
""", unsafe_allow_html=True)
            
            st.markdown(badge_html, unsafe_allow_html=True)
            
            st.markdown("### 📊 주요 펀더멘털 및 기술 지표")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric(label="현재 주가", value=fmt_price(current_price), delta=f"{drawdown:.2f}% (최고가대비)")
                with c2: st.metric(label=f"적정 주가 ({model_used})", value=fmt_price(final_fair_value) if final_fair_value != "N/A" else "N/A", 
                                   delta=f"{margin_of_safety:.2f}% (안전마진)" if margin_of_safety != "N/A" else None,
                                   help="테크/성장주는 현금흐름할인(DCF) 모델로, 가치/배당주는 그레이엄 모델로 자동 산출됩니다.")
                with c3: st.metric(label="1년 MDD (최대 낙폭)", value=f"{mdd:.2f}%", delta="Max Drawdown", delta_color="inverse")
                with c4: st.metric(label="EPS (주당순이익)", value=fmt_price(eps) if eps else "N/A", 
                                   help="1주당 회사가 벌어들인 순이익을 의미해요. 숫자가 클수록 회사의 기업 가치가 크고, 배당 줄 수 있는 여유가 늘어났다고 볼 수 있어요.")
                    
            with st.container(border=True):
                c5, c6, c7, c8 = st.columns(4)
                with c5: st.metric(label="PBR", value=pbr if isinstance(pbr, str) else f"{pbr:.2f}배", 
                                   help="주가가 1주당 장부상 순자산가치의 몇 배로 거래되는지 나타냅니다. 1 미만이면 회사를 다 팔아도 남는 돈보다 주가가 싸다는 뜻(저평가)입니다.")
                with c6: st.metric(label="ROE", value=f"{roe*100:.2f}%" if roe is not None else "N/A", 
                                   help="회사가 주주의 돈(자본)을 굴려서 1년간 얼마를 벌었는지 보여주는 핵심 수익성 지표입니다. (통상 15% 이상이면 우량 기업으로 평가)")
                with c7: st.metric(label="52주 최고가", value=fmt_price(high_1y))
                with c8: st.metric(label="52주 최저가", value=fmt_price(low_1y))
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("### 👔 Professional Insights (전문가 핵심 지표)")
            with st.container(border=True):
                pc1, pc2, pc3, pc4 = st.columns(4)
                
                peg_val = f"{peg_ratio:.2f}배" if peg_ratio else "N/A"
                peg_delta = ("저평가 구간" if peg_ratio and peg_ratio <= 1.0 else "고평가 구간") if peg_ratio else None
                peg_help_text = "PER(주가수익비율)을 이익성장률로 나눈 값입니다. 보통 1.0 이하이면 기업의 미래 성장 속도에 비해 현재 주가가 싸다(저평가)고 판단합니다."
                if peg_ratio is None: 
                    peg_help_text += "\n\n🚨 [N/A 발생 이유]\n야후 파이낸스에 향후 5년 이익성장률 추정치가 누락되어 있거나 해당 기업이 적자 상태이기 때문입니다."
                
                fcf_val = "N/A"
                if fcf is not None:
                    fcf_conv = fcf * ex_rate if is_krw else fcf
                    if is_krw: fcf_val = f"₩{fcf_conv/1e12:.2f}조" if fcf_conv >= 1e12 else (f"₩{fcf_conv/1e8:.2f}억" if fcf_conv >= 1e8 else f"₩{fcf_conv:,.0f}")
                    else: fcf_val = f"${fcf/1e12:.2f}T" if fcf >= 1e12 else (f"${fcf/1e9:.2f}B" if fcf >= 1e9 else f"${fcf/1e6:.2f}M")
                
                payout_val = f"{payout_ratio * 100:.1f}%" if payout_ratio else "N/A"
                inst_val = f"{info.get('heldPercentInstitutions', 0) * 100:.1f}%" if info.get('heldPercentInstitutions') else "N/A"

                with pc1: st.metric(label="PEG Ratio (성장성 대비 가치)", value=peg_val, delta=peg_delta, delta_color="normal" if peg_ratio and peg_ratio <= 1.0 else "inverse", help=peg_help_text)
                with pc2: st.metric(label="Free Cash Flow (잉여현금흐름)", value=fcf_val, delta="현금창출 긍정적" if fcf and fcf > 0 else "우려", delta_color="normal" if fcf and fcf > 0 else "inverse", help="회사가 필수적인 투자를 다 하고도 통장에 남는 순수한 잉여 여윳돈입니다. 이 돈으로 배당을 주거나 빚을 갚을 수 있어 아주 중요합니다.")
                with pc3: st.metric(label="Payout Ratio (배당 성향)", value=payout_val, delta="건전" if payout_ratio and payout_ratio <= 0.6 else "과부하 우려", delta_color="normal" if payout_ratio and payout_ratio <= 0.6 else "inverse", help="순이익 중 주주들에게 배당금으로 나눠주는 비율입니다. 너무 높으면 미래 투자가 어렵고 배당 삭감 위험이 있습니다.")
                with pc4: st.metric(label="Inst. Ownership (기관 보유율)", value=inst_val, help="월가 기관 투자자(헤지펀드, 연기금 등)들이 이 회사 주식을 얼마나 쥐고 있는지를 나타냅니다. 50% 이상이면 주도적 매수세가 있다고 봅니다.")
                
                st.markdown("<hr style='margin: 15px 0; border-color: #30363d;'>", unsafe_allow_html=True)
                st.markdown("<p style='color:#8b949e; font-weight:bold; margin-bottom:10px;'>🔍 알파 스프레드 기반 상대가치 지표 (Relative Valuation Multiples)</p>", unsafe_allow_html=True)
                
                rc1, rc2, rc3, rc4 = st.columns(4)
                with rc1: st.metric(label="EV/EBITDA (현금창출비율)", value=f"{ev_ebitda:.2f}배" if ev_ebitda else "N/A", help="기업가치(부채포함)를 영업이익(EBITDA)으로 나눈 값입니다. 보통 10배 이하일 때 저평가로 봅니다.")
                with rc2: st.metric(label="P/S Ratio (주가/매출액)", value=f"{ps_ratio:.2f}배" if ps_ratio else "N/A", help="시가총액을 연간 매출액으로 나눈 배수입니다. 이익이 안 나는 고성장 기업의 상대적 몸값을 잴 때 필수적입니다.")
                with rc3: st.metric(label="EV/Revenue (기업가치/매출)", value=f"{ev_revenue:.2f}배" if ev_revenue else "N/A", help="기업가치를 매출액으로 나눈 값으로, P/S보다 부채까지 고려하여 더 정교하게 몸값을 잽니다.")
                with rc4: st.metric(label="Forward P/E (선행 PER)", value=f"{forward_pe:.2f}배" if forward_pe else "N/A", help="향후 1년 예상 순이익 대비 주가가 몇 배인지 나타냅니다. 과거 실적보다 미래의 기대치를 엿볼 수 있습니다.")
            
            with st.expander("💡 알파 스프레드 4대 핵심 지표 완벽 해독 가이드", expanded=False):
                ev_e_text = f"{ev_ebitda:.2f}배" if ev_ebitda else "N/A"
                ps_text = f"{ps_ratio:.2f}배" if ps_ratio else "N/A"
                ev_r_text = f"{ev_revenue:.2f}배" if ev_revenue else "N/A"
                fwd_pe_text = f"{forward_pe:.2f}배" if forward_pe else "N/A"
                
                ev_e_years = f"약 {int(ev_ebitda)}년" if ev_ebitda else "알 수 없는 기간"
                ev_e_eval = "꽤 비싼(고평가)" if ev_ebitda and ev_ebitda > 10 else "저렴한(저평가)"
                pe_eval = "시장 평균 대비 비싸게" if forward_pe and forward_pe > 15 else "시장 평균 대비 저렴하게"
                
                st.markdown(f"""
                **① EV/EBITDA (현재 {ev_e_text})**
                * **의미:** "내가 이 회사를 통째로 인수했을 때, 이 회사가 영업으로 벌어들이는 현금(EBITDA)으로 내 투자금을 전부 회수하는 데 몇 년이 걸릴까?"를 뜻합니다.
                * **기준치:** 통상적으로 월가에서는 **'10배 이하'**를 저평가(싸다)로 봅니다.
                * **해석:** 현재 {ev_e_text}면 투자금 회수까지 {ev_e_years}이 걸린다는 뜻이므로, 절대적인 기준으로는 {ev_e_eval} 상태입니다. (단, AI나 테크 기업들은 미래 성장이 확실해서 20배 이상을 받는 경우가 흔합니다.)
                
                **② P/S Ratio & ③ EV/Revenue (현재 {ps_text}, {ev_r_text})**
                * **의미:** 두 지표 모두 "이 회사가 1년 동안 파는 '매출액' 대비 덩치(시가총액/기업가치)가 몇 배인가?"를 봅니다. (아직 순이익은 적자지만 매출이 폭발적으로 늘어나는 기업을 평가할 때 주로 씁니다.)
                * **기준치:** 업종마다 완전히 다릅니다. 이마트 같은 유통업/제조업은 1배 미만이 정상입니다. 반면 마진율이 엄청난 소프트웨어(SaaS), AI 기업은 5~10배를 정상으로 봅니다.
                * **해석:** 매출액의 {ps_text}에 거래되고 있다는 것은, 이 회사가 이익을 엄청나게 많이 남기는 독점적인 테크/소프트웨어 기업이라는 것을 시장이 인정해주고 있다는 뜻이거나, 혹은 심각한 고평가 상태임을 의미합니다.
                
                **④ Forward P/E (선행 PER) (현재 {fwd_pe_text})**
                * **의미:** "내년(향후 1년) 예상 순이익 대비 주가가 몇 배로 거래되는가?"를 뜻합니다. 가장 대중적인 지표입니다.
                * **기준치:** 미국 S&P 500 시장 전체의 역사적 평균은 대략 15배 ~ 18배 수준입니다.
                * **해석:** 평균인 15배를 기준으로 볼 때 현재 {fwd_pe_text}이므로 {pe_eval} 거래되고 있습니다. 향후 성장에 대한 투자자들의 프리미엄이 반영된 수치입니다.
                """)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("### ⚖️ 동종 업계 멀티플 비교 (Peer Valuation)")
            
            peer_df = get_peers_data(ticker, peer_input)
            
            if not peer_df.empty:
                median_pe = peer_df['Fwd P/E'].median()
                median_ev_ebitda = peer_df['EV/EBITDA'].median()
                median_ps = peer_df['P/S'].median()
                median_ev_rev = peer_df['EV/Rev'].median()
                
                table_html = "<table class='peer-table'><tr><th>Ticker</th><th>Price (현재 주가)</th><th>Forward P/E (선행 PER)</th><th>EV/EBITDA (현금창출비율)</th><th>P/S Ratio (주가/매출액)</th><th>EV/Revenue (기업가치/매출)</th></tr>"
                
                for _, row in peer_df.iterrows():
                    is_main = row['Ticker'] == ticker
                    row_class = "peer-main-row" if is_main else ""
                    table_html += f"<tr class='{row_class}'>"
                    table_html += f"<td>{row['Ticker']}</td>"
                    table_html += f"<td>{fmt_price(row['Price'])}</td>"
                    table_html += f"<td>{fmt_multi(row['Fwd P/E'])}</td>"
                    table_html += f"<td>{fmt_multi(row['EV/EBITDA'])}</td>"
                    table_html += f"<td>{fmt_multi(row['P/S'])}</td>"
                    table_html += f"<td>{fmt_multi(row['EV/Rev'])}</td>"
                    table_html += "</tr>"
                
                table_html += "<tr class='peer-median-row'>"
                table_html += "<td>산업 중앙값 (Median)</td>"
                table_html += "<td>-</td>"
                table_html += f"<td>{fmt_multi(median_pe)}</td>"
                table_html += f"<td>{fmt_multi(median_ev_ebitda)}</td>"
                table_html += f"<td>{fmt_multi(median_ps)}</td>"
                table_html += f"<td>{fmt_multi(median_ev_rev)}</td>"
                table_html += "</tr></table>"
                
                with st.container(border=True):
                    st.markdown(table_html, unsafe_allow_html=True)
            else:
                st.warning("경쟁사 데이터를 불러올 수 없습니다.")
                
            st.markdown("<br>", unsafe_allow_html=True)

            if not hist_10y.empty and final_fair_value != "N/A":
                df_10y = hist_10y[['Close']].copy()
                df_10y.rename(columns={'Close': 'Price'}, inplace=True)
                latest_date = df_10y.index[-1]
                years_diff = (latest_date - df_10y.index).days / 365.25
                df_10y['Value'] = final_fair_value / ((1 + g/100) ** years_diff)
                df_10y['Over_Top'] = np.maximum(df_10y['Price'], df_10y['Value'])
                df_10y['Under_Bottom'] = np.minimum(df_10y['Price'], df_10y['Value'])

                if is_krw:
                    df_10y['Value'] *= ex_rate
                    df_10y['Over_Top'] *= ex_rate
                    df_10y['Under_Bottom'] *= ex_rate
                    df_10y['Price'] *= ex_rate

                fig_val = go.Figure()
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Over_Top'], fill='tonexty', fillcolor='rgba(239, 83, 80, 0.3)', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Under_Bottom'], line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], fill='tonexty', fillcolor='rgba(102, 187, 106, 0.3)', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Price'], mode='lines', line=dict(color='#29b6f6', width=2), name='실제 주가 (Price)'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], mode='lines', line=dict(color='#ffa726', width=2, dash='dot'), name=f'추정 내재가치 ({model_used})'))

                fig_val.update_layout(
                    title=dict(text="📊 10 YR Price to Intrinsic Value Variance Analysis", font=dict(size=20), x=0.5, xanchor='center'),
                    hovermode="x unified", height=550, margin=dict(l=0, r=0, t=50, b=0),
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                    yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right', tickprefix="₩" if is_krw else "$"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                with st.container(border=True): st.plotly_chart(fig_val, use_container_width=True)

            plot_hist_1y = hist_1y.copy()
            if is_krw:
                for col in ['Open', 'High', 'Low', 'Close', 'SMA50', 'SMA200']: plot_hist_1y[col] *= ex_rate

            st.markdown("<br>### 📉 최근 1년 주가 일봉 차트 (SMA 50, SMA 200)", unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=plot_hist_1y.index, open=plot_hist_1y['Open'], high=plot_hist_1y['High'], low=plot_hist_1y['Low'], close=plot_hist_1y['Close'], increasing_line_color='#ef5350', decreasing_line_color='#42a5f5', name=f"{ticker} 캔들"))
            fig.add_trace(go.Scatter(x=plot_hist_1y.index, y=plot_hist_1y['SMA50'], mode='lines', line=dict(color='#ffd600', width=1.5), name='50일 이동평균'))
            fig.add_trace(go.Scatter(x=plot_hist_1y.index, y=plot_hist_1y['SMA200'], mode='lines', line=dict(color='#00b0ff', width=1.5), name='200일 이동평균'))
            
            fig.update_layout(
                xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=10, b=0),
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right', tickprefix="₩" if is_krw else "$"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            with st.container(border=True): st.plotly_chart(fig, use_container_width=True)
                
            if not df_wk.empty:
                plot_df_wk = df_wk.copy()
                if is_krw:
                    for col in ['Open', 'High', 'Low', 'Close', 'MA10', 'MA20', 'MA60', 'MA120', 'ATR_Stop']: plot_df_wk[col] *= ex_rate

                st.markdown("<br><br>### 🔭 트레이딩뷰 주봉 차트", unsafe_allow_html=True)
                fig_wk = go.Figure()
                fig_wk.add_trace(go.Candlestick(x=plot_df_wk.index, open=plot_df_wk['Open'], high=plot_df_wk['High'], low=plot_df_wk['Low'], close=plot_df_wk['Close'], increasing_line_color='#ef5350', decreasing_line_color='#42a5f5', name=f"{ticker} 주봉"))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk.index, y=plot_df_wk['MA10'], mode='lines', line=dict(color='#ab47bc', width=1.5), name='10주선'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk.index, y=plot_df_wk['MA20'], mode='lines', line=dict(color='#ffd600', width=1.5), name='20주선'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk.index, y=plot_df_wk['MA60'], mode='lines', line=dict(color='#00e676', width=2.5), name='60주선'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk.index, y=plot_df_wk['MA120'], mode='lines', line=dict(color='#8d6e63', width=1.5), name='120주선'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk.index, y=plot_df_wk['ATR_Stop'], mode='lines', line=dict(color='#ff9800', width=2, dash='dot'), name='ATR 스탑 방어선'))
                
                y_main = plot_df_wk[df_wk['Signal_Main']]['Low'] * 0.92
                y_re = plot_df_wk[df_wk['Signal_Reentry']]['Low'] * 0.92
                y_sell = plot_df_wk[df_wk['Signal_Sell']]['High'] * 1.08
                
                fig_wk.add_trace(go.Scatter(x=plot_df_wk[df_wk['Signal_Main']].index, y=y_main, mode='markers', marker=dict(symbol='triangle-up', color='red', size=20), name=' 매수 타점'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk[df_wk['Signal_Reentry']].index, y=y_re, mode='markers', marker=dict(symbol='triangle-up', color='#00e676', size=16), name=' 재진입 타점'))
                fig_wk.add_trace(go.Scatter(x=plot_df_wk[df_wk['Signal_Sell']].index, y=y_sell, mode='markers', marker=dict(symbol='triangle-down', color='#29b6f6', size=16), name=' 매도 타점'))
                
                fig_wk.update_layout(
                    xaxis_rangeslider_visible=False, height=650, margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                    yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right', tickprefix="₩" if is_krw else "$"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                with st.container(border=True): st.plotly_chart(fig_wk, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 🤖 수석 비서의 AI 종합 브리핑 (Tier 1)")
            if st.button("✨ 퀀트 데이터 기반 AI 분석 보고서 작성", type="primary", width="stretch"):
                with st.spinner(f"[{ticker}]의 데이터와 경쟁사 비교표를 분석하여 AI 브리핑을 작성 중입니다... 🧠"):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.7, "max_output_tokens": 8000})
                        ai_median_pe = f"{median_pe:.2f}배" if not peer_df.empty else "데이터 없음"
                        
                        prompt = f"""
                        당신은 수석 퀀트 애널리스트입니다. [{ticker}] 분석 데이터를 브리핑해주세요.
                        - 터미널 점수: 10점 만점에 {score}점 ({judgment})
                        - 적용된 모델: {model_used} / 안전마진: {margin_of_safety if margin_of_safety == "N/A" else f"{margin_of_safety:.1f}%"}
                        - 해당 기업 Forward P/E: {forward_pe}배 / 동종 업계 경쟁사 Forward P/E 중앙값: {ai_median_pe}
                        - ROE: {roe*100:.1f}% / 현재 미국 국채 금리: {risk_free_rate:.2f}%
                        
                        [작성 규칙]
                        1. 시작: "대표님, [{ticker}] 퀀트 데이터 종합 분석 보고드립니다."
                        2. 체질 평가: 왜 이 기업이 {model_used}로 평가되었는지(성장/가치) 설명하세요.
                        3. 핵심 분석: 안전마진과 함께, 해당 기업의 P/E가 동종업계 중앙값보다 싼지 비싼지(상대가치)를 비교하여 매력도를 개조식(~함, ~됨)으로 분석하세요.
                        4. 별표(*)와 이모지 사용 금지. 대괄호([ ]) 사용.
                        5. 마침표(.) 뒤에는 무조건 줄바꿈(엔터).
                        6. 마지막 줄: "💡 수석 비서의 최종 투자의견:" 이라는 항목 달고 1줄 요약 결론.
                        """
                        response = model.generate_content(prompt)
                        st.success("✅ 종합 브리핑 완료!")
                        with st.container(border=True):
                            clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', response.text.replace("*", "")).replace(". ", ".\n\n")
                            st.markdown(clean_text)
                    except Exception as e: st.error(f"🚨 AI 오류: {e}")

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
