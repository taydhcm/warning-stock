import time
import streamlit as st
import pandas as pd
import numpy as np
import pandas_ta as ta
from vnstock import Vnstock, register_user
from datetime import datetime, timedelta
import requests
import warnings

warnings.filterwarnings('ignore')

# ====================== CẤU HÌNH ======================
st.set_page_config(page_title="Warning System", layout="wide")
st.title("🚨 Warning System - Cảnh báo vị thế đã mua")
st.markdown("**Quét 3 timeframe • Tự động 5 phút • Gửi Telegram**")

# Đăng ký API Key vnstock
VNSTOCK_API_KEY = "vnstock_9008899a9dce77c13e296b6442ee866c"
try:
    register_user(api_key=VNSTOCK_API_KEY)
except:
    pass

# ====================== TELEGRAM CONFIG ======================
if 'telegram_token' not in st.session_state:
    st.session_state.telegram_token = ""
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = ""

with st.sidebar.expander("📲 Cài đặt Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Telegram Bot Token", 
        value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID", 
        value=st.session_state.telegram_chat_id)

    if st.button("Test Telegram"):
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            try:
                requests.get(f"https://api.telegram.org/bot{st.session_state.telegram_token}/sendMessage",
                    params={"chat_id": st.session_state.telegram_chat_id, "text": "✅ Test thành công từ Warning System"})
                st.success("Đã gửi test message!")
            except:
                st.error("Gửi test thất bại")
        else:
            st.warning("Vui lòng nhập Token và Chat ID")

# ====================== TRỌNG SỐ & HÀM CHẤM ĐIỂM (giữ nguyên từ trước) ======================
WEIGHTS = {'Momentum': 0.30, 'Trend': 0.22, 'Volume': 0.18,
           'Oscillator': 0.15, 'Volatility': 0.08, 'PriceAction': 0.07}

# (Bạn copy 6 hàm score_xxx từ file trade.py cũ vào đây - score_momentum, score_trend, ...)
# (Giữ nguyên 6 hàm score_momentum, score_trend, score_oscillator, score_volume, score_volatility, score_price_action như file cũ của bạn)
# ====================== HÀM CHẤM ĐIỂM (0-10) ======================
def score_momentum(crsi, price_vs_hvn):
    if crsi > 68 and price_vs_hvn == "above_hvn": return 9.5
    elif crsi > 55 and price_vs_hvn in ["near_hvn", "above_hvn"]: return 8.0
    elif 45 <= crsi <= 55: return 6.5
    else: return 4.0

def score_trend(price, ma20_series, ma50_series):
    ma20 = ma20_series.iloc[-1]
    ma50 = ma50_series.iloc[-1]
    ma20_prev = ma20_series.iloc[-2] if len(ma20_series) > 1 else ma20
    if price > ma20 > ma50 and ma20 > ma20_prev:
        return 9.5
    elif price > ma20 > ma50:
        return 7.8
    elif ma20 > price > ma50:
        return 5.5
    elif ma20 > ma50:
        return 4.5
    else:
        return 3.0

def score_oscillator(rsi, stoch):
    if 48 <= rsi <= 68 and stoch > 55: return 9.0
    elif 40 <= rsi <= 72 and stoch > 40: return 7.0
    elif rsi > 72 or rsi < 35 or stoch < 20: return 4.0
    else: return 5.5

def score_volume(obv_trend, volume_increase):
    if obv_trend == "up" and volume_increase: return 9.5
    elif obv_trend == "flat" and volume_increase: return 7.5
    elif obv_trend == "up": return 6.5
    elif obv_trend == "down": return 4.0
    else: return 5.5

def score_volatility(bb_status, band_width):
    if bb_status == "squeeze" and band_width < 0.08: return 9.0
    elif bb_status == "normal": return 6.5
    elif bb_status == "expansion": return 5.0
    else: return 4.0

def score_price_action(pa_signal, near_support):
    if pa_signal == "strong_bounce" and near_support: return 9.5
    elif pa_signal in ["hammer", "engulfing"] and near_support: return 8.0
    elif pa_signal == "neutral" and near_support: return 6.0
    elif pa_signal == "neutral": return 5.5
    else: return 3.5

# ====================== HÀM LẤY DỮ LIỆU (Cache 5 phút) ======================
@st.cache_data(ttl=300)  # Cache 5 phút
def get_data(symbol, interval="1h", days=60):
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = Vnstock().stock(symbol=symbol).quote.history(start=start, end=end, interval=interval)
        return df
    except:
        return pd.DataFrame()

# ====================== GIAO DIỆN QUẢN LÝ VỊ THẾ ======================
st.sidebar.header("📌 Danh sách cổ phiếu đã mua")

# Lưu danh sách holdings trong session_state
if 'holdings' not in st.session_state:
    st.session_state.holdings = []

# Form thêm mới
with st.sidebar.form("add_holding"):
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Mã CK", placeholder="VHM")
    with col2:
        buy_price = st.number_input("Giá mua", min_value=0.0, value=100.0, step=0.1)
    submitted = st.form_submit_button("➕ Thêm vào danh sách")
    if submitted and symbol:
        st.session_state.holdings.append({"Mã": symbol.upper(), "Giá mua": buy_price})
        st.success(f"Đã thêm {symbol}")

# Hiển thị danh sách hiện tại
st.sidebar.subheader("Danh sách hiện tại")
for i, item in enumerate(st.session_state.holdings):
    col1, col2, col3 = st.sidebar.columns([3, 2, 1])
    with col1:
        st.write(f"**{item['Mã']}** - {item['Giá mua']}")
    with col3:
        if st.button("🗑", key=f"del_{i}"):
            st.session_state.holdings.pop(i)
            st.rerun()

# ====================== NÚT QUÉT ======================
if st.button("🚨 Quét cảnh báo ngay", type="primary", use_container_width=True):
    if not st.session_state.holdings:
        st.error("Chưa có cổ phiếu nào trong danh sách")
    else:
        with st.spinner("Đang quét 3 timeframe..."):
            results = []
            for holding in st.session_state.holdings:
                symbol = holding["Mã"]
                buy_price = holding["Giá mua"]

                df_30m = get_data(symbol, "30m", 30)
                df_1h = get_data(symbol, "1h", 60)
                df_4h = get_data(symbol, "4h", 120)

                current_price = df_1h['close'].iloc[-1] if not df_1h.empty else buy_price

                # Tính điểm (dùng df_1h làm chính)
                view_scores = calculate_view_scores(df_1h, current_price, df_1h['low'].rolling(20).min().iloc[-1] if not df_1h.empty else 0)
                final_score = calculate_weighted_score(view_scores)

                recommend = "NẮM GIỮ" if final_score >= 7.0 else "BÁN" if final_score <= 5.5 else "THEO DÕI"

                # Gửi Telegram nếu là tín hiệu BÁN
                if recommend == "BÁN" and st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    msg = f"🚨 CẢNH BÁO BÁN\nMã: {symbol}\nGiá mua: {buy_price}\nGiá hiện tại: {current_price:.2f}\nFinal Score: {final_score}\nKhuyến nghị: BÁN"
                    try:
                        requests.get(f"https://api.telegram.org/bot{st.session_state.telegram_token}/sendMessage",
                                     params={"chat_id": st.session_state.telegram_chat_id, "text": msg, "parse_mode": "HTML"})
                    except:
                        pass

                results.append({
                    "Mã CK": symbol,
                    "Giá mua": buy_price,
                    "Giá hiện tại": round(current_price, 2),
                    "Final Score": final_score,
                    "Khuyến nghị": recommend,
                    "Ngành nghề": get_sector(symbol)
                })

            df_result = pd.DataFrame(results)
            st.success(f"✅ Đã quét {len(results)} cổ phiếu")

            st.dataframe(
                df_result.style.background_gradient(subset=['Final Score'], cmap='RdYlGn'),
                use_container_width=True,
                height=600
            )

# Tự động refresh mỗi 5 phút
st.caption("Auto refresh mỗi 5 phút • Telegram alert khi có tín hiệu BÁN")
