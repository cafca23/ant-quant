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
</style>
""", unsafe_allow_html=True)

# 💡 [핵심] 실시간 거시경제 데이터 (환율 & 미국 10년물 국채 금리)
@st.cache_data(ttl=3600, show_spinner=False)
def get_macro_data():
    try:
        usdkrw = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
    except: usdkrw = 1350.0
    try:
        tnx = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    except: tnx = 4.2  # 통신 실패 시 기본 금리
    return float(usdkrw), float(tnx)

# Data fetching function
@st.cache_data(ttl=3600, show_spinner="티커 재무 데이터를 분석하고 있습니다...")
def get_stock_market_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="2y")
    hist_10y = stock.history(period="10y", interval="1mo")
    hist_daily_5y = stock.history(period="5y", interval="1d")
    hist_weekly = hist_daily_5y.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna() if not hist_daily_5y.empty else pd.DataFrame()
    return info, hist, hist_10y, hist_weekly

# 매크로 데이터 로드
ex_rate, risk_free_rate = get_macro_data()

# 사이드바
with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    ticker_input = st.text_input("종목 티커 입력 (예: AAPL, PLTR, KO)", value="AAPL")
    
    currency_opt = st.radio("💱 표시 통화", ["$ 달러", "₩ 원화"], horizontal=True)
    is_krw = currency_opt == "₩ 원화"
    
    st.divider()
    
    # 💡 [핵심] 실시간 금리 기반 할인율(WACC) 자동 세팅
    st.markdown("### 🌐 거시경제(매크로) 연동")
    st.info(f"실시간 美 10년물 국채 금리: **{risk_free_rate:.2f}%**")
    default_wacc = round(risk_free_rate + 5.0, 1) # 국채 금리 + 시장 위험 프리미엄 5%
    
    discount_rate = st.slider("DCF 할인율 (금리 반영) %", min_value=1.0, max_value=20.0, value=default_wacc, step=0.1, 
                              help="미래의 현금흐름을 현재 가치로 땡겨올 때 깎는 비율입니다. (자동으로 '국채 금리 + 5%' 로 셋팅됩니다.)")
    
    st.divider()
    
    default_g = 15.0
    sgr_caption = "💡 AI 추천 성장률: 정보 없음 (기본값 15.0% 적용)"
    
    if ticker_input:
        ticker_for_sidebar = ticker_input.upper()
        try:
            info_sb, _, _, _ = get_stock_market_data(ticker_for_sidebar)
            roe_sb = info_sb.get('returnOnEquity', 0)
            payout_sb = info_sb.get('payoutRatio', 0)
            if roe_sb is not None and roe_sb > 0:
                sgr = roe_sb * (1 - payout_sb) * 100
                sgr = max(5.0, min(sgr, 50.0))
                default_g = float(round(sgr, 1))
                sgr_caption = f"💡 자동 추천 성장률(SGR 기반): {default_g}%"
        except: pass

    if 'last_ticker' not in st.session_state or st.session_state.last_ticker != ticker_input:
        st.session_state.g_slider = default_g
        st.session_state.last_ticker = ticker_input
        
    def set_g(val): st.session_state.g_slider = val

    g = st.slider("예상 성장률 (g) %", min_value=0.0, max_value=50.0, step=0.5, key="g_slider", help="기업의 향후 5~10년 기대 성장률")
    c1, c2, c3, c4 = st.columns(4)
    c1.button("10", on_click=set_g, args=(10.0,), width="stretch")
    c2.button("20", on_click=set_g, args=(20.0,), width="stretch")
    c3.button("30", on_click=set_g, args=(30.0,), width="stretch")
    c4.button("40", on_click=set_g, args=(40.0,), width="stretch")
    st.button("🔄 SGR 기반 (AI추천)", on_click=set_g, args=(default_g,), width="stretch")
    st.caption(sgr_caption)

# 포맷팅 도우미
def fmt_price(val):
    if val == "N/A" or val is None: return "N/A"
    if is_krw: return f"₩{val * ex_rate:,.0f}"
    return f"${val:,.2f}"

# --- 메인 로직 ---
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.markdown("<h1 style='margin-bottom: 0; font-size: 2.0rem;'>📈 앤트리치 퀀트 터미널</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8b949e; font-size: 1.05rem; margin-top: 5px;'>월스트리트 DCF + 그레이엄 하이브리드 엔진</p>", unsafe_allow_html=True)

if ticker_input:
    ticker = ticker_input.upper()
    try:
        info, hist, hist_10y, hist_weekly = get_stock_market_data(ticker)
        
        if hist.empty or len(hist) < 200:
            st.error("데이터가 부족하거나 티커가 올바르지 않습니다.")
        else:
            # 기술적 지표 계산
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
            
            # 재무 지표
            eps = info.get('trailingEps', info.get('forwardEps', 0))
            pbr = info.get('priceToBook', 'N/A')
            roe = info.get('returnOnEquity', None)
            debt_to_equity = info.get('debtToEquity', None)
            peg_ratio = info.get('pegRatio', None)
            fcf = info.get('freeCashflow', None)
            payout_ratio = info.get('payoutRatio', 0)
            if payout_ratio is None: payout_ratio = 0
            shares = info.get('sharesOutstanding', None)
            sector = info.get('sector', '')
            
            # 💡 [핵심] AI 종목 체질 판독 로직 (가치주 vs 성장주)
            is_growth = (payout_ratio < 0.15) or ("Technology" in sector) or ("Communication" in sector) or (peg_ratio and peg_ratio > 1.5)
            
            # 1. 그레이엄 적정 주가 계산
            graham_value = "N/A"
            if eps is not None and eps > 0: 
                graham_value = eps * (8.5 + 2 * g)
                
            # 2. 월가식 간편 DCF 적정 주가 계산
            dcf_value = "N/A"
            if fcf is not None and fcf > 0 and shares is not None:
                wacc = discount_rate / 100
                g_dec = g / 100
                term_g = 0.025 # 영구 성장률 2.5%
                
                pv_fcf = 0
                for i in range(1, 6):
                    pv_fcf += (fcf * ((1 + g_dec) ** i)) / ((1 + wacc) ** i)
                tv = (fcf * ((1 + g_dec) ** 5) * (1 + term_g)) / max((wacc - term_g), 0.001)
                pv_tv = tv / ((1 + wacc) ** 5)
                
                total_equity = pv_fcf + pv_tv
                dcf_value = total_equity / shares
                
            # 💡 [핵심] 체질에 따른 메인 가치 자동 스위칭
            if is_growth and dcf_value != "N/A":
                final_fair_value = dcf_value
                model_used = "DCF(현금흐름할인) 모델"
                badge_html = "<div class='badge badge-growth'>🚀 AI 판독: 테크/성장주 트랙 적용 중</div>"
            else:
                final_fair_value = graham_value
                model_used = "벤저민 그레이엄 모델"
                badge_html = "<div class='badge badge-value'>🏛️ AI 판독: 전통 가치/배당주 트랙 적용 중</div>"
                
            margin_of_safety = "N/A"
            if final_fair_value != "N/A":
                margin_of_safety = ((final_fair_value - current_price) / abs(final_fair_value)) * 100

            hist_1y = hist.tail(252).copy()
            high_1y = hist_1y['High'].max()
            low_1y = hist_1y['Low'].min()
            drawdown = ((current_price - high_1y) / high_1y) * 100
            
            roll_max = hist_1y['Close'].cummax()
            daily_drawdown = hist_1y['Close'] / roll_max - 1.0
            mdd = daily_drawdown.min() * 100
            
            # 주봉 타점 및 스코어 계산 (이전과 동일 로직)
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

            score = 0
            checklist = []
            
            if margin_of_safety != "N/A":
                if margin_of_safety > 20:   
                    score += 2; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+2"})
                elif margin_of_safety > 0:  
                    score += 1; checklist.append({"status": "pass", "category": "가치", "desc": f"적정주가 대비 안전마진 {margin_of_safety:.1f}%", "score": "+1"})
                else:                       
                    checklist.append({"status": "fail", "category": "가치", "desc": "고평가 상태 (안전마진 부족)", "score": "0"})
            else:
                checklist.append({"status": "info", "category": "가치", "desc": "적정 주가 산출 불가 (데이터 부족)", "score": "-"})
                
            if roe is not None and roe > 0.15: score += 2; checklist.append({"status": "pass", "category": "수익성", "desc": f"ROE 15% 초과 ({roe*100:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "수익성", "desc": f"ROE 15% 미달", "score": "0"})
                
            if debt_to_equity is not None and debt_to_equity < 100: score += 2; checklist.append({"status": "pass", "category": "건전성", "desc": f"안정적인 부채비율 ({debt_to_equity:.1f}%)", "score": "+2"})
            else: checklist.append({"status": "fail", "category": "건전성", "desc": f"부채비율 높음", "score": "0"})
                
            if pd.notna(sma50_val) and pd.notna(sma200_val):
                if current_price > sma50_val and sma50_val > sma200_val: score += 3; checklist.append({"status": "pass", "category": "일봉 추세", "desc": "정배열 상승 (주가 > 50일선 > 200일선)", "score": "+3"})
                elif current_price > sma50_val and sma50_val <= sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "바닥 반등 시작 (주가 > 50일선)", "score": "+1"})
                elif current_price <= sma50_val and current_price > sma200_val: score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "장기 상승장 속 조정 (눌림목)", "score": "+1"})
                else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "완전 역배열 (단기/장기 하락세)", "score": "0"})
            else: checklist.append({"status": "fail", "category": "일봉 추세", "desc": "추세 판독 불가", "score": "0"})
                
            if pd.notna(rsi_val) and rsi_val < 70: score += 1; checklist.append({"status": "pass", "category": "단기 수급", "desc": f"RSI 70 미만 과열 아님 ({rsi_val:.1f})", "score": "+1"})
            else: checklist.append({"status": "fail", "category": "단기 수급", "desc": "RSI 단기 과열 상태", "score": "0"})

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
                with c4: st.metric(label="EPS (주당순이익)", value=fmt_price(eps) if eps else "N/A", help="1주당 회사가 벌어들인 순이익을 의미해요.")
                    
            with st.container(border=True):
                c5, c6, c7, c8 = st.columns(4)
                with c5: st.metric(label="PBR", value=pbr if isinstance(pbr, str) else f"{pbr:.2f}", help="주가가 장부상 순자산가치의 몇 배인지 나타냅니다.")
                with c6: st.metric(label="ROE", value=f"{roe*100:.2f}%" if roe is not None else "N/A", help="회사가 주주의 돈으로 1년간 얼마를 벌었는지 보여줍니다.")
                with c7: st.metric(label="52주 최고가", value=fmt_price(high_1y))
                with c8: st.metric(label="52주 최저가", value=fmt_price(low_1y))
                    
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 👔 Professional Insights (전문가 핵심 지표)")
            with st.container(border=True):
                pc1, pc2, pc3, pc4 = st.columns(4)
                peg_val = f"{peg_ratio:.2f}" if peg_ratio else "N/A"
                peg_delta = ("저평가 구간" if peg_ratio <= 1.0 else "고평가 구간") if peg_ratio else None
                
                fcf_val = "N/A"
                if fcf is not None:
                    fcf_conv = fcf * ex_rate if is_krw else fcf
                    if is_krw: fcf_val = f"₩{fcf_conv/1e12:.2f}조" if fcf_conv >= 1e12 else (f"₩{fcf_conv/1e8:.2f}억" if fcf_conv >= 1e8 else f"₩{fcf_conv:,.0f}")
                    else: fcf_val = f"${fcf/1e12:.2f}T (조)" if fcf >= 1e12 else (f"${fcf/1e9:.2f}B (십억)" if fcf >= 1e9 else f"${fcf/1e6:.2f}M (백만)")
                
                payout_val = f"{payout_ratio * 100:.1f}%" if payout_ratio else "N/A"
                inst_val = f"{info.get('heldPercentInstitutions', 0) * 100:.1f}%" if info.get('heldPercentInstitutions') else "N/A"

                with pc1: st.metric(label="PEG Ratio", value=peg_val, delta=peg_delta, delta_color="normal" if peg_ratio and peg_ratio <= 1.0 else "inverse", help="이익성장률 대비 주가. 1.0 이하면 저평가로 봅니다.")
                with pc2: st.metric(label="Free Cash Flow", value=fcf_val, delta="현금창출 긍정적" if fcf and fcf > 0 else "우려", delta_color="normal" if fcf and fcf > 0 else "inverse", help="필수 투자를 마치고 남은 순수 잉여현금입니다.")
                with pc3: st.metric(label="Payout Ratio", value=payout_val, delta="건전" if payout_ratio and payout_ratio <= 0.6 else "과부하 우려", delta_color="normal" if payout_ratio and payout_ratio <= 0.6 else "inverse")
                with pc4: st.metric(label="Inst. Ownership", value=inst_val, help="월가 기관 투자자들의 보유 비율입니다.")
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- AI 수석 비서 브리핑 ---
            st.markdown("### 🤖 수석 비서의 AI 종합 브리핑 (Tier 1)")
            if st.button("✨ 퀀트 데이터 기반 AI 분석 보고서 작성", type="primary", width="stretch"):
                with st.spinner(f"[{ticker}]의 재무 데이터와 실시간 금리를 바탕으로 AI 브리핑을 작성 중입니다... 🧠"):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.7, "max_output_tokens": 8000})
                        
                        prompt = f"""
                        당신은 수석 퀀트 애널리스트입니다. [{ticker}] 분석 데이터를 브리핑해주세요.
                        - 터미널 점수: 10점 만점에 {score}점 ({judgment})
                        - 적용된 적정주가 모델: {model_used}
                        - 적정주가 대비 안전마진: {margin_of_safety if margin_of_safety == "N/A" else f"{margin_of_safety:.1f}%"}
                        - ROE: {roe*100:.1f}% / PEG: {peg_val} / 현재 미국 국채 금리(무위험수익률): {risk_free_rate:.2f}%
                        
                        [작성 규칙]
                        1. 시작: "대표님, [{ticker}] 퀀트 데이터 종합 분석 보고드립니다."
                        2. 체질 평가: 왜 이 기업이 {model_used}로 평가되었는지(성장주인지 가치주인지) 설명하세요.
                        3. 핵심 분석: 안전마진과 현재 매크로 금리({risk_free_rate:.2f}%) 상황을 엮어서 주가의 매력도를 개조식(~함, ~됨)으로 분석하세요.
                        4. 별표(*)와 이모지 사용 금지. 대괄호([ ]) 사용.
                        5. 마침표(.) 뒤에는 무조건 줄바꿈(엔터) 할 것.
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
