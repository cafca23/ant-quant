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
    /* Metric styling adjustments */
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700 !important;
        color: #e6edf3;
    }
    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        font-size: 0.85rem !important;
        letter-spacing: 0.05em;
    }
    
    /* Professional Banner Classes */
    .banner {
        padding: 1.5rem;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .buy-banner { background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%); color: white; border: 1px solid #1565c0; } 
    .hold-banner { background: linear-gradient(135deg, #052e16 0%, #166534 100%); color: white; border: 1px solid #15803d; }
    .sell-banner { background: linear-gradient(135deg, #450a0a 0%, #991b1b 100%); color: white; border: 1px solid #b91c1c; } 
    
    .banner h2 { margin: 0; padding: 0; font-size: 2.2rem; text-shadow: 0 2px 4px rgba(0,0,0,0.4); }
    .banner p { margin: 8px 0 0 0; font-size: 1.15rem; opacity: 0.95; font-weight: 500;}
    
    .checklist-box {
        background-color: #161b22;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #30363d;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .check-item { margin-bottom: 8px; font-size: 1rem; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.markdown("<h1 style='margin-bottom: 0; font-size: 2.0rem;'>📈 앤트리치 퀀트 터미널</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8b949e; font-size: 1.05rem; margin-top: 5px;'>월스트리트 결합 퀀트 평가 시스템 (AI 엔진 탑재)</p>", unsafe_allow_html=True)

# Data fetching function MUST be defined before sidebar calls it
@st.cache_data(ttl=3600, show_spinner="티커 재무 데이터를 분석하고 있습니다...")
def get_stock_market_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="2y")
    hist_10y = stock.history(period="10y", interval="1mo")
    
    hist_daily_5y = stock.history(period="5y", interval="1d")
    if not hist_daily_5y.empty:
        hist_weekly = hist_daily_5y.resample('W-FRI').agg({
            'Open': 'first', 
            'High': 'max', 
            'Low': 'min', 
            'Close': 'last'
        }).dropna()
    else:
        hist_weekly = pd.DataFrame()
        
    return info, hist, hist_10y, hist_weekly

# 사이드바
with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    ticker_input = st.text_input("종목 티커 입력 (예: AAPL, PLTR, QQQ)", value="AAPL")
    
    default_g = 15.0
    sgr_caption = "💡 AI 추천 성장률: 정보 없음 (기본값 15.0% 적용)"
    
    if ticker_input:
        ticker_for_sidebar = ticker_input.upper()
        try:
            info_sb, _, _, _ = get_stock_market_data(ticker_for_sidebar)
            roe_sb = info_sb.get('returnOnEquity', None)
            payout_sb = info_sb.get('payoutRatio', 0)
            if payout_sb is None: payout_sb = 0
            
            if roe_sb is not None:
                sgr = roe_sb * (1 - payout_sb) * 100
                if sgr < 5.0: sgr = 5.0
                elif sgr > 50.0: sgr = 50.0
                
                default_g = float(round(sgr, 1))
                sgr_caption = f"💡 자동 추천 성장률(SGR 기반): {default_g}%"
        except:
            pass

    if 'last_ticker' not in st.session_state or st.session_state.last_ticker != ticker_input:
        st.session_state.g_slider = default_g
        st.session_state.last_ticker = ticker_input
        
    def set_g(val):
        st.session_state.g_slider = val

    g = st.slider("예상 성장률 (g) %", min_value=0.0, max_value=50.0, step=0.5, key="g_slider",
                  help="벤저민 그레이엄 공식에 적용할 향후 7~10년 장기 기대 성장률")
                  
    c1, c2, c3, c4 = st.columns(4)
    # 💡 최신 문법 패치: use_container_width -> width="stretch" (지원 버전 호환성을 위해 유지하되, 내부 최적화)
    c1.button("10", on_click=set_g, args=(10.0,), use_container_width=True)
    c2.button("20", on_click=set_g, args=(20.0,), use_container_width=True)
    c3.button("30", on_click=set_g, args=(30.0,), use_container_width=True)
    c4.button("40", on_click=set_g, args=(40.0,), use_container_width=True)
    
    st.button("🔄 SGR 기반", on_click=set_g, args=(default_g,), use_container_width=True, help="해당 종목의 AI 권장 성장률로 복원")

    st.caption(sgr_caption)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.expander("💡 10점 만점 채점 기준", expanded=True):
        st.markdown("""
        **[ 월가 거장 모델 결합 시스템 ]**
        - 가치: 안전마진 >20% (+2), >0% (+1)
        - 수익성: ROE > 15% (+2)
        - 건전성: 부채비율 < 100% (+2)
        - 추세: 주가가 SMA 200 위에 위치 (+2)
        - 타이밍: SMA 50 > SMA 200 정배열 (+1)
        - 리스크: RSI(14) < 70 과열방지 (+1)
        """)

if ticker_input:
    ticker = ticker_input.upper()
    try:
        info, hist, hist_10y, hist_weekly = get_stock_market_data(ticker)
        
        if hist.empty or len(hist) < 200:
            st.error("데이터가 부족하거나 티커가 올바르지 않습니다. (SMA 계산을 위해 200일 이상 데이터 필요)")
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
            payout_ratio = info.get('payoutRatio', None)
            inst_own = info.get('heldPercentInstitutions', None)
            
            value_graham = "N/A"
            margin_of_safety = "N/A"
            if eps is not None: 
                value_graham = eps * (8.5 + 2 * g)
                
                if value_graham != 0:
                    margin_of_safety = ((value_graham - current_price) / abs(value_graham)) * 100
                else:
                    margin_of_safety = -100.0
                
            hist_1y = hist.tail(252).copy()
            high_1y = hist_1y['High'].max()
            low_1y = hist_1y['Low'].min()
            drawdown = ((current_price - high_1y) / high_1y) * 100
            
            roll_max = hist_1y['Close'].cummax()
            daily_drawdown = hist_1y['Close'] / roll_max - 1.0
            mdd = daily_drawdown.min() * 100
            
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
                    prev_c = close_val[i-1]
                    prev_s = atr_stop[i-1]
                    cur_c = calc_val[i]
                    
                    if np.isnan(prev_s): atr_stop[i] = cur_c
                    elif prev_c > prev_s: atr_stop[i] = max(cur_c, prev_s)
                    else: atr_stop[i] = cur_c
                        
                df_wk['ATR_Stop'] = atr_stop
                
                ma_stack = df_wk[['MA10', 'MA20', 'MA60']]
                convergence_ratio = (ma_stack.max(axis=1) - ma_stack.min(axis=1)) / ma_stack.min(axis=1)
                df_wk['Converged'] = convergence_ratio.round(4) <= 0.0700
                
                df_wk['Bullish'] = df_wk['Close'] > df_wk['Open']
                df_wk['Prev_MA10'] = df_wk['MA10'].shift(1)
                df_wk['Prev_MA20'] = df_wk['MA20'].shift(1)
                df_wk['Prev_ATR_Stop'] = df_wk['ATR_Stop'].shift(1)
                
                df_wk['Signal_Main'] = (
                    df_wk['Converged'] & 
                    (df_wk['Close'] > df_wk['MA20']) & 
                    (df_wk['Close'] > df_wk['MA60']) & 
                    (df_wk['MA60'] >= df_wk['MA120']) & 
                    (df_wk['Close'] > df_wk['ATR_Stop'])
                )
                df_wk['Signal_Main'] = df_wk['Signal_Main'] & (~df_wk['Signal_Main'].shift(1).fillna(False))
                
                cross_up_10 = (df_wk['Prev_Close'] <= df_wk['Prev_MA10']) & (df_wk['Close'] > df_wk['MA10'])
                ma20_rising = df_wk['MA20'] > df_wk['Prev_MA20']
                df_wk['Signal_Reentry'] = (
                    (df_wk['Close'] > df_wk['MA60']) &
                    cross_up_10 & df_wk['Bullish'] & ma20_rising &
                    (df_wk['Close'] > df_wk['ATR_Stop']) &
                    (~df_wk['Signal_Main'])
                )
                
                df_wk['Signal_Sell'] = (df_wk['Prev_Close'] >= df_wk['Prev_ATR_Stop']) & (df_wk['Close'] < df_wk['ATR_Stop'])

            score = 0
            checklist = []
            
            if margin_of_safety != "N/A":
                if eps is not None and eps < 0:
                    checklist.append({"status": "info", "category": "가치", "desc": "적정 주가 산출 불가 (EPS 순이익 적자)", "score": "-"})
                else:
                    if margin_of_safety > 20:   
                        score += 2; checklist.append({"status": "pass", "category": "가치", "desc": f"내재가치 대비 안전마진 {margin_of_safety:.1f}%", "score": "+2"})
                    elif margin_of_safety > 0:  
                        score += 1; checklist.append({"status": "pass", "category": "가치", "desc": f"내재가치 대비 안전마진 {margin_of_safety:.1f}%", "score": "+1"})
                    else:                       
                        checklist.append({"status": "fail", "category": "가치", "desc": "고평가 상태 (안전마진 부족)", "score": "0"})
            else:
                checklist.append({"status": "info", "category": "가치", "desc": "적정 주가 산출 불가 (EPS 부족)", "score": "-"})
                
            if roe is not None and roe > 0.15:
                score += 2; checklist.append({"status": "pass", "category": "수익성", "desc": f"ROE 15% 초과 ({roe*100:.1f}%)", "score": "+2"})
            else:
                roe_str = f"{roe*100:.1f}%" if roe is not None else "정보 없음"
                checklist.append({"status": "fail", "category": "수익성", "desc": f"ROE 15% 미달 ({roe_str})", "score": "0"})
                
            if debt_to_equity is not None and debt_to_equity < 100:
                score += 2; checklist.append({"status": "pass", "category": "건전성", "desc": f"안정적인 부채비율 ({debt_to_equity:.1f}%)", "score": "+2"})
            else:
                de_str = f"{debt_to_equity:.1f}%" if debt_to_equity is not None else "정보 없음"
                checklist.append({"status": "fail", "category": "건전성", "desc": f"부채비율 높음 ({de_str})", "score": "0"})
                
            if pd.notna(sma50_val) and pd.notna(sma200_val):
                if current_price > sma50_val and sma50_val > sma200_val:
                    score += 3; checklist.append({"status": "pass", "category": "일봉 추세", "desc": "정배열 상승 (주가 > 50일선 > 200일선)", "score": "+3"})
                elif current_price > sma50_val and sma50_val <= sma200_val:
                    score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "바닥 반등 시작 (주가 > 50일선)", "score": "+1"})
                elif current_price <= sma50_val and current_price > sma200_val:
                    score += 1; checklist.append({"status": "info", "category": "일봉 추세", "desc": "장기 상승장 속 조정 (눌림목)", "score": "+1"})
                else:
                    checklist.append({"status": "fail", "category": "일봉 추세", "desc": "완전 역배열 (단기/장기 하락세)", "score": "0"})
            else:
                checklist.append({"status": "fail", "category": "일봉 추세", "desc": "데이터 부족으로 추세 판독 불가", "score": "0"})
                
            if not df_wk.empty:
                if df_wk['Signal_Main'].iloc[-1]:
                    checklist.append({"status": "info", "category": "주봉 타점", "desc": "60주선 기반 매수 타점 포착!", "score": "-"})
                elif df_wk['Signal_Reentry'].iloc[-1]:
                    checklist.append({"status": "info", "category": "주봉 타점", "desc": "10주선 기반 추가 매수 타점 포착!", "score": "-"})
                if df_wk['Signal_Sell'].iloc[-1]:
                    checklist.append({"status": "fail", "category": "주봉 리스크", "desc": "ATR 방어선 이탈 (매도 경고)", "score": "-"})
                    
            if pd.notna(rsi_val) and rsi_val < 70:
                score += 1; checklist.append({"status": "pass", "category": "단기 수급", "desc": f"RSI 70 미만으로 단기 과열 아님 ({rsi_val:.1f})", "score": "+1"})
            else:
                checklist.append({"status": "fail", "category": "단기 수급", "desc": "RSI 단기 과열 상태 구간진입", "score": "0"})

            if score >= 8:
                judgment = "🌟 강력 매수 (Strong Buy)"; banner_class = "buy-banner"; prog_color = "#1976d2"
            elif score >= 5:
                judgment = "🟢 분할 매수 / 관망 (Accumulate/Hold)"; banner_class = "hold-banner"; prog_color = "#166534"
            else:
                judgment = "🔴 매도 / 주의 (Sell/Warning)"; banner_class = "sell-banner"; prog_color = "#b91c1c"
            
            short_name = info.get('shortName', ticker)
            
            st.markdown(f"""
<div class="banner {banner_class}">
    <h2>{short_name} ({ticker})</h2>
    <p>퀀트 평가 등급: <b style="font-size:1.3rem;">{judgment}</b> &nbsp;|&nbsp; 월가 거장 결합 스코어 : <b>{score} 점</b> </p>
</div>
""", unsafe_allow_html=True)
            
            items_html_list = []
            for item in checklist:
                st_color = "#3fb950" if item["status"] == "pass" else ("#f85149" if item["status"] == "fail" else "#d29922")
                st_bg = "rgba(63, 185, 80, 0.15)" if item["status"] == "pass" else ("rgba(248, 81, 73, 0.15)" if item["status"] == "fail" else "rgba(210, 153, 34, 0.15)")
                icon = "✅" if item["status"] == "pass" else ("❌" if item["status"] == "fail" else "💡")
                
                html_snippet = f'''<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; margin-bottom: 8px; background-color: #161b22; border-radius: 6px; border-left: 4px solid {st_color}; border-top: 1px solid #30363d; border-right: 1px solid #30363d; border-bottom: 1px solid #30363d;">
    <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
        <span style="font-size: 1.1rem;">{icon}</span>
        <span style="background-color: {st_bg}; color: {st_color}; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; min-width: 50px; text-align: center;">{item["category"]}</span>
        <span style="color: #c9d1d9; font-size: 0.95rem;">{item["desc"]}</span>
    </div>
    <div style="font-weight: bold; color: {st_color}; font-size: 1.05rem; min-width: 45px; text-align: right;">{item["score"]}점</div>
</div>'''
                items_html_list.append(html_snippet)
                
            items_html = "".join(items_html_list)
            dashboard_html = f"""
<div style="display: flex; gap: 20px; align-items: stretch; margin-bottom: 20px; flex-wrap: wrap;">
    <div class='checklist-box' style='flex: 1 1 300px; text-align:center; display: flex; flex-direction: column; justify-content: center;'>
        <h3 style='margin:0 0 10px 0; color:#8b949e;'>TOTAL SCORE</h3>
        <h1 style='font-size: 5rem; margin:10px 0; color:{prog_color};'>{score}<span style='font-size: 2.5rem; color:#8b949e;'> / 10</span></h1>
        <div style="width:100%; background-color:#30363d; border-radius:10px; margin-top:15px; margin-bottom: 10px;">
            <div style="width:{min(score*10, 100)}%; background-color:{prog_color}; height:24px; border-radius:10px; transition: 1s ease;"></div>
        </div>
    </div>
    <div class='checklist-box' style='flex: 1.8 1 500px; justify-content: flex-start;'>
        <h3 style='margin:0 0 15px 0; color:#8b949e;'>평가 내용</h3>
        {items_html}
    </div>
</div>
"""
            st.markdown(dashboard_html, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # ==========================================
            # 💡 [툴팁 고도화] 펀더멘털 및 기술 지표 설명 추가
            # ==========================================
            st.markdown("### 📊 주요 펀더멘털 및 기술 지표")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric(label="현재 주가", value=f"${current_price:,.2f}", delta=f"{drawdown:.2f}% (최고가대비)")
                with c2: st.metric(label="적정 주가", value=f"${value_graham:,.2f}" if value_graham != "N/A" else "N/A", 
                                   delta=f"{margin_of_safety:.2f}% (안전마진)" if margin_of_safety != "N/A" else None)
                with c3: st.metric(label="1년 MDD (최대 낙폭)", value=f"{mdd:.2f}%", delta="Max Drawdown", delta_color="inverse")
                with c4: st.metric(label="EPS (주당순이익)", value=f"${eps:,.2f}" if eps else "N/A", 
                                   help="1주당 회사가 벌어들인 순이익을 의미해요. 숫자가 클수록 회사의 기업 가치가 크고, 배당 줄 수 있는 여유가 늘어났다고 볼 수 있어요.")
                    
            with st.container(border=True):
                c5, c6, c7, c8 = st.columns(4)
                with c5: st.metric(label="PBR", value=pbr if isinstance(pbr, str) else f"{pbr:.2f}", 
                                   help="주가가 1주당 장부상 순자산가치의 몇 배로 거래되는지 나타냅니다. 1 미만이면 회사를 다 팔아도 남는 돈보다 주가가 싸다는 뜻(저평가)입니다.")
                with c6: st.metric(label="ROE", value=f"{roe*100:.2f}%" if roe is not None else "N/A", 
                                   help="회사가 주주들의 돈(자본)을 굴려서 1년간 얼마를 벌었는지 보여주는 핵심 수익성 지표입니다. (통상 15% 이상이면 우량 기업으로 평가)")
                with c7: st.metric(label="52주 최고가", value=f"${high_1y:,.2f}")
                with c8: st.metric(label="52주 최저가", value=f"${low_1y:,.2f}")
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("### 👔 Professional Insights (전문가 핵심 지표)")
            if peg_ratio is not None:
                peg_val = f"{peg_ratio:.2f}"
                if peg_ratio <= 1.0: peg_delta = "저평가 구간 (Good)"; peg_color = "normal"
                else: peg_delta = "고평가 구간 (Bad)"; peg_color = "inverse"
            else:
                peg_val = "N/A"; peg_delta = None; peg_color = "off"
                
            if fcf is not None:
                if fcf >= 1e12: fcf_val = f"${fcf/1e12:.2f}T (조)"
                elif fcf >= 1e9: fcf_val = f"${fcf/1e9:.2f}B (십억)"
                else: fcf_val = f"${fcf/1e6:.2f}M (백만)"
                fcf_delta = "현금창출 긍정적" if fcf > 0 else "현금유출 우려"
                fcf_color = "normal" if fcf > 0 else "inverse"
            else:
                fcf_val = "N/A"; fcf_delta = None; fcf_color = "off"
                
            if payout_ratio is not None:
                payout_val = f"{payout_ratio * 100:.1f}%"
                if payout_ratio <= 0.6: payout_delta = "건전한 배당 수준"; payout_color = "normal"
                else: payout_delta = "배당 과부하 우려"; payout_color = "inverse"
            else:
                payout_val = "N/A"; payout_delta = None; payout_color = "off"
                
            if inst_own is not None:
                inst_val = f"{inst_own * 100:.1f}%"
                inst_delta = "주도적 기관 매수세" if inst_own > 0.5 else "개인 위주 수급"
                inst_color = "normal" if inst_own > 0.5 else "off"
            else:
                inst_val = "N/A"; inst_delta = None; inst_color = "off"
                
            with st.container(border=True):
                pc1, pc2, pc3, pc4 = st.columns(4)
                with pc1: st.metric(label="PEG Ratio (성장성 대비 가치)", value=peg_val, delta=peg_delta, delta_color=peg_color, 
                                    help="PER(주가수익비율)을 이익성장률로 나눈 값입니다. 보통 1.0 이하이면 기업의 미래 성장 속도에 비해 현재 주가가 싸다(저평가)고 판단합니다.")
                with pc2: st.metric(label="Free Cash Flow (잉여현금흐름)", value=fcf_val, delta=fcf_delta, delta_color=fcf_color, 
                                    help="회사가 필수적인 투자를 다 하고도 통장에 남는 순수한 잉여 여윳돈입니다. 이 돈으로 배당을 주거나 빚을 갚을 수 있어 아주 중요합니다.")
                with pc3: st.metric(label="Payout Ratio (배당 성향)", value=payout_val, delta=payout_delta, delta_color=payout_color, 
                                    help="회사가 한 해 동안 번 순이익 중에서 몇 %를 주주들에게 배당금으로 나눠주는지를 나타냅니다. 너무 높으면 미래 투자가 어렵고 배당 삭감 위험이 있습니다.")
                with pc4: st.metric(label="Inst. Ownership (기관 보유율)", value=inst_val, delta=inst_delta, delta_color=inst_color, 
                                    help="월가 기관 투자자(헤지펀드, 연기금 등)들이 이 회사 주식을 얼마나 쥐고 있는지를 나타냅니다. 50% 이상이면 주도적 매수세가 있다고 봅니다.")
                
            st.markdown("<br>", unsafe_allow_html=True)

            if not hist_10y.empty and value_graham != "N/A":
                df_10y = hist_10y[['Close']].copy()
                df_10y.rename(columns={'Close': 'Price'}, inplace=True)
                
                latest_date = df_10y.index[-1]
                days_diff = (latest_date - df_10y.index).days
                years_diff = days_diff / 365.25
                
                df_10y['Value'] = value_graham / ((1 + g/100) ** years_diff)
                df_10y['Over_Top'] = np.maximum(df_10y['Price'], df_10y['Value'])
                df_10y['Under_Bottom'] = np.minimum(df_10y['Price'], df_10y['Value'])

                fig_val = go.Figure()
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Over_Top'], fill='tonexty', fillcolor='rgba(239, 83, 80, 0.3)', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Under_Bottom'], line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], fill='tonexty', fillcolor='rgba(102, 187, 106, 0.3)', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Price'], mode='lines', line=dict(color='#29b6f6', width=2), name='실제 주가 (Price)'))
                fig_val.add_trace(go.Scatter(x=df_10y.index, y=df_10y['Value'], mode='lines', line=dict(color='#ffa726', width=2, dash='dot'), name='비례 추정 내재가치 (Value)'))

                fig_val.update_layout(
                    title=dict(text="📊 10 YR Price to Intrinsic Value Variance Analysis", font=dict(size=20), x=0.5, xanchor='center'),
                    hovermode="x unified",
                    height=550,
                    margin=dict(l=0, r=0, t=50, b=0),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                    yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right'),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                with st.container(border=True):
                    st.plotly_chart(fig_val, use_container_width=True)
                    st.caption("※ 초록색 구간: 추정 내재가치 대비 저평가(언더슈팅) 구간 | ※ 빨간색 구간: 고평가(오버슈팅) 구간")

                st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("### 📉 최근 1년 주가 일봉 차트 (SMA 50, SMA 200)")
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(x=hist_1y.index,
                            open=hist_1y['Open'], high=hist_1y['High'], low=hist_1y['Low'], close=hist_1y['Close'],
                            increasing_line_color='#ef5350', decreasing_line_color='#42a5f5',
                            name=f"{ticker} 캔들"))
                            
            fig.add_trace(go.Scatter(x=hist_1y.index, y=hist_1y['SMA50'], mode='lines', line=dict(color='#ffd600', width=1.5), name='50일 이동평균'))
            fig.add_trace(go.Scatter(x=hist_1y.index, y=hist_1y['SMA200'], mode='lines', line=dict(color='#00b0ff', width=1.5), name='200일 이동평균'))
            
            fig.update_layout(
                xaxis_rangeslider_visible=False,
                height=600,
                margin=dict(l=0, r=0, t=10, b=0),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            with st.container(border=True):
                st.plotly_chart(fig, use_container_width=True)
                
            if not df_wk.empty:
                st.markdown("<br><br>", unsafe_allow_html=True)
                st.markdown("### 🔭 트레이딩뷰 주봉 차트")
                st.markdown("<p style='color:#8b949e; font-size:0.95rem; margin-top:-5px;'> 매수 타점 |  재진입 타점 |  매도 액션 &nbsp;|&nbsp; <b>선풍기: MA10(보라), MA20(노랑), MA60(초록), MA120(갈색), ATR스탑(주황점선)</b></p>", unsafe_allow_html=True)
                
                fig_wk = go.Figure()
                
                fig_wk.add_trace(go.Candlestick(x=df_wk.index,
                    open=df_wk['Open'], high=df_wk['High'], low=df_wk['Low'], close=df_wk['Close'],
                    increasing_line_color='#ef5350', decreasing_line_color='#42a5f5', name=f"{ticker} 주봉"))
                    
                fig_wk.add_trace(go.Scatter(x=df_wk.index, y=df_wk['MA10'], mode='lines', line=dict(color='#ab47bc', width=1.5), name='10주선'))
                fig_wk.add_trace(go.Scatter(x=df_wk.index, y=df_wk['MA20'], mode='lines', line=dict(color='#ffd600', width=1.5), name='20주선'))
                fig_wk.add_trace(go.Scatter(x=df_wk.index, y=df_wk['MA60'], mode='lines', line=dict(color='#00e676', width=2.5), name='60주선'))
                fig_wk.add_trace(go.Scatter(x=df_wk.index, y=df_wk['MA120'], mode='lines', line=dict(color='#8d6e63', width=1.5), name='120주선'))
                fig_wk.add_trace(go.Scatter(x=df_wk.index, y=df_wk['ATR_Stop'], mode='lines', line=dict(color='#ff9800', width=2, dash='dot'), name='ATR 스탑 방어선'))
                
                y_main = df_wk[df_wk['Signal_Main']]['Low'] * 0.92
                y_re = df_wk[df_wk['Signal_Reentry']]['Low'] * 0.92
                y_sell = df_wk[df_wk['Signal_Sell']]['High'] * 1.08
                
                fig_wk.add_trace(go.Scatter(x=df_wk[df_wk['Signal_Main']].index, y=y_main, mode='markers', marker=dict(symbol='triangle-up', color='red', size=20), name=' 매수 타점'))
                fig_wk.add_trace(go.Scatter(x=df_wk[df_wk['Signal_Reentry']].index, y=y_re, mode='markers', marker=dict(symbol='triangle-up', color='#00e676', size=16), name=' 재진입 타점'))
                fig_wk.add_trace(go.Scatter(x=df_wk[df_wk['Signal_Sell']].index, y=y_sell, mode='markers', marker=dict(symbol='triangle-down', color='#29b6f6', size=16), name=' 매도 타점'))
                
                fig_wk.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=650,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d'),
                    yaxis=dict(showgrid=True, gridcolor='#30363d', zerolinecolor='#30363d', side='right'),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                with st.container(border=True):
                    st.plotly_chart(fig_wk, use_container_width=True)

            # ==========================================
            # 💡 [핵심 고도화] AI 수석 비서의 브리핑 엔진 이식
            # ==========================================
            st.divider()
            st.markdown("### 🤖 수석 비서의 AI 종합 브리핑 (Tier 1)")
            st.caption("위의 모든 퀀트 수치와 차트 지표를 AI가 종합 분석하여 투자 의견을 도출합니다.")
            
            if st.button("✨ 퀀트 데이터 기반 AI 분석 보고서 작성", type="primary", use_container_width=True):
                with st.spinner(f"[{ticker}]의 모든 재무 및 차트 데이터를 AI 두뇌로 전송하여 분석 중입니다... 🧠"):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        generation_config = {"temperature": 0.7, "max_output_tokens": 8000}
                        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
                        
                        margin_str = f"{margin_of_safety:.2f}%" if margin_of_safety != "N/A" else "산출 불가"
                        roe_str = f"{roe*100:.2f}%" if roe is not None else "데이터 없음"
                        
                        prompt = f"""
                        당신은 월스트리트 출신의 수석 퀀트 애널리스트이자 나의 직속 비서입니다.
                        다음은 방금 터미널에서 연산된 [{ticker}] 종목의 핵심 퀀트 데이터입니다.

                        [퀀트 분석 데이터]
                        - 터미널 종합 평가: 10점 만점에 {score}점 ({judgment})
                        - 그레이엄 적정 주가 대비 안전마진: {margin_str}
                        - 1년 최대 낙폭 (MDD): {mdd:.2f}%
                        - ROE (자기자본이익률): {roe_str}
                        - PEG Ratio (성장성 대비 가치): {peg_val}

                        위 수치들을 완벽하게 융합하여, 대표님(사용자)에게 보고하는 형식으로 핵심만 날카롭게 브리핑해 주세요.

                        [🚨 작성 규칙]
                        1. 도입부: "대표님, [{ticker}] 퀀트 데이터 종합 분석 결과 보고드립니다." 로 시작하세요.
                        2. 데이터 해석: 왜 {score}점이 나왔는지, 현재 주가가 저평가인지 고평가인지, 리스크(MDD, PEG 등) 측면에서 위 수치를 어떻게 해석해야 하는지 개조식(~함, ~됨)으로 명확히 분석하세요.
                        3. 기호 통제: 글 전체에 걸쳐 별표(*)와 이모티콘(이모지)은 단 한 개도 절대 사용하지 마세요. 강조는 대괄호([ ])나 꺾쇠(【 】)만 사용하세요.
                        4. [줄바꿈 강제]: 가독성을 위해 본문을 작성할 때 문장이 마침표(.)로 끝나면, 무조건 줄바꿈(엔터)을 하여 다음 내용이 새로운 줄에서 시작되도록 하세요.
                        5. 결론: 맨 마지막 줄에 "💡 수석 비서의 최종 투자의견:" 이라는 항목을 달고, 당장 매수해야 할지, 관망해야 할지, 매도해야 할지 1줄 요약으로 냉철하게 보고하세요.
                        """
                        
                        response = model.generate_content(prompt)
                        st.success("✅ 무제한 엔진(Tier 1) 종합 브리핑 완료!")
                        
                        with st.container(border=True):
                            # 💡 파이썬 물리적 살균 및 100% 강제 줄바꿈
                            clean_text = response.text.replace("*", "")
                            clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', clean_text)
                            clean_text = clean_text.replace(". ", ".\n\n")
                            st.markdown(clean_text)
                            
                    except Exception as e:
                        st.error(f"🚨 AI 분석 중 오류가 발생했습니다: {e}")

    except Exception as e:
        import traceback
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        st.code(traceback.format_exc())
