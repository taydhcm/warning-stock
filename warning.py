import time
import streamlit as st
import pandas as pd
import numpy as np
import pandas_ta as ta
from vnstock import Vnstock, register_user
from datetime import datetime, timedelta
import requests
import warnings
import os
import json

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Warning System", layout="wide")
st.title("🚨 Warning System - Cảnh báo vị thế đã mua")
st.markdown("**Quét 3 timeframe • Tự động 5 phút • Gửi Telegram**")
# ====================== DICTIONARY NGÀNH NGHỀ ======================
SECTOR_MAP = {
    "ACB": "Ngân hàng", "BID": "Ngân hàng", "VCB": "Ngân hàng", "CTG": "Ngân hàng", 
    "HDB": "Ngân hàng", "MBB": "Ngân hàng", "SHB": "Ngân hàng", "STB": "Ngân hàng",
    "TCB": "Ngân hàng", "TPB": "Ngân hàng", "VPB": "Ngân hàng", "LPB": "Ngân hàng",
    "OCB": "Ngân hàng", "VIB": "Ngân hàng",

    "HPG": "Thép - Vật liệu xây dựng", "HSG": "Thép", "NKG": "Thép",
    "VHM": "Bất động sản", "VIC": "Bất động sản", "NVL": "Bất động sản", 
    "PDR": "Bất động sản", "KBC": "Bất động sản", "DIG": "Bất động sản",
    "VRE": "Bất động sản", "DXG": "Bất động sản",

    "FPT": "Công nghệ - Thông tin", "MWG": "Bán lẻ", "PNJ": "Bán lẻ",
    "FRT": "Bán lẻ", "DGW": "Bán lẻ",

    "MSN": "Thực phẩm - Đồ uống", "VNM": "Sữa - Thực phẩm", "SAB": "Đồ uống",
    "QNS": "Đường", "SBT": "Đường", "LSS": "Đường",

    "POW": "Điện lực", "GAS": "Khí đốt", "PLX": "Xăng dầu",
    "VJC": "Hàng không", "TCH": "Ô tô - Linh kiện",

    "SSI": "Chứng khoán", "VCI": "Chứng khoán",

    "GEX": "Vật liệu xây dựng", "DGC": "Hóa chất", "DPM": "Phân bón",
    "DCM": "Phân bón", "BFC": "Phân bón",

    "ANV": "Thủy sản", "VHC": "Thủy sản",

    "REE": "Điện lạnh - Cơ điện", "GEG": "Điện", "PC1": "Xây dựng",

    "KDH": "Bất động sản", "NLG": "Bất động sản", "TTA": "Bất động sản",
    "HDG": "Bất động sản", "BCG": "Bất động sản",

    "SAM": "Dệt may", "TNG": "Dệt may", "VGT": "Dệt may",

    "PET": "Nhựa - Hóa chất", "CSV": "Nhựa", "LAS": "Nhựa",

    "PVS": "Dầu khí", "PVD": "Dầu khí", "PVT": "Vận tải biển",
    "HAH": "Vận tải", "VOS": "Vận tải",

    "SCS": "Logistics", "VSC": "Vận tải",
}

def get_sector(symbol):
    return SECTOR_MAP.get(symbol, "Khác / Chưa phân loại")
# ====================== VNSTOCK API KEY ======================
VNSTOCK_API_KEY = "vnstock_9008899a9dce77c13e296b6442ee866c"
try:
    register_user(api_key=VNSTOCK_API_KEY)
    st.success("✅ Đã đăng ký vnstock API key", icon="🔑")
except:
    pass

# ====================== TELEGRAM CONFIG ======================
if 'telegram_token' not in st.session_state:
    st.session_state.telegram_token = "8516741675:AAE8rdixZX6x7e-ZtXXH1YjZC-PehUFkLOA"
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = "1247850754"

with st.sidebar.expander("📲 Telegram Alert", expanded=False):
    st.session_state.telegram_token = st.text_input("token bot telegram", 
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

# ====================== LOAD DANH SÁCH TỪ FILE list.env ======================
HOLDINGS_FILE = "list.env"

def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except:
            return []
    return []

def save_holdings(holdings):
    with open(HOLDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)

# Load danh sách khi khởi động
if 'holdings' not in st.session_state:
    st.session_state.holdings = load_holdings()

# ====================== TRỌNG SỐ MỚI (TỐI ƯU CHO CẢNH BÁO BÁN) ======================
WEIGHTS = {
    'Momentum':   0.32,   # Quan trọng nhất khi nắm giữ
    'Volume':     0.25,   # Dòng tiền khô = dấu hiệu bán mạnh
    'Trend':      0.18,
    'Oscillator': 0.12,
    'PriceAction':0.08,
    'Volatility': 0.05
}

# ====================== TRỌNG SỐ MỚI (TẬP TRUNG CẢNH BÁO BÁN) ======================
WEIGHTS = {
    'Momentum':   0.33,   # Quan trọng nhất cho tín hiệu bán sớm
    'Volume':     0.27,   # Dòng tiền khô = bán mạnh
    'PriceAction':0.18,   # Phá support = bán khẩn
    'Trend':      0.12,
    'Oscillator': 0.10,
    'Volatility': 0.00   # Giảm trọng số vì ngắn hạn ít quan trọng
}

# ====================== HÀM CHẤM ĐIỂM MỚI (NHẠY HƠN) ======================
def score_momentum(crsi):
    if crsi > 68: return 9.5
    elif crsi > 58: return 8.0
    elif crsi > 50: return 6.0
    elif crsi < 45: return 3.0   # Momentum yếu = nguy cơ bán
    else: return 5.0

def score_volume(obv_trend, vol_ratio):
    if obv_trend == "down": return 3.5          # OBV giảm = bán
    if obv_trend == "up" and vol_ratio > 1.4: return 9.0
    if vol_ratio < 0.8: return 4.0              # Volume khô
    return 6.0

def score_price_action(current_price, support, prev_close):
    if current_price < support * 0.985: return 3.0   # Phá support = bán khẩn
    if current_price < prev_close * 0.99: return 4.5 # Giá giảm
    if current_price > support * 1.015: return 8.5
    return 5.5

def score_trend(price, ma20):
    if price > ma20: return 7.5
    else: return 4.5

def score_oscillator(rsi):
    if rsi > 72: return 3.5   # Quá mua → dễ điều chỉnh
    if rsi < 35: return 4.0
    if 48 <= rsi <= 65: return 8.0
    return 5.5

def score_volatility(band_width):
    if band_width < 0.07: return 8.0   # Co hẹp → sắp biến động
    if band_width > 0.18: return 4.5   # Biến động lớn
    return 6.0

# ====================== TÍNH ĐIỂM TRÊN 1 TIMEFRAME ======================
def calculate_view_scores(df, current_price, support):
    if df is None or df.empty or len(df) < 30:
        return {k: 5.0 for k in WEIGHTS.keys()}

    try:
        close = df['close']
        ma20 = close.rolling(20).mean().iloc[-1]
        rsi = ta.rsi(close, length=14).iloc[-1]
        stoch = ta.stoch(df['high'], df['low'], close)['STOCHk_14_3_3'].iloc[-1] if len(df) > 14 else 50.0

        obv = ta.obv(close, df['volume'])
        obv_trend = "up" if obv.diff().iloc[-1] > 0 else "down" if obv.diff().iloc[-1] < 0 else "flat"
        vol_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1] if len(df) > 20 else 1.0

        crsi = ta.crsi(close, df['high'], df['low'], length=3, fast=2, slow=100).iloc[-1] if len(df) > 100 else 50.0

        bb = ta.bbands(close, length=20, std=2)
        band_width = (bb['BBU_20_2.0'].iloc[-1] - bb['BBL_20_2.0'].iloc[-1]) / current_price if not bb.empty else 0.12

        prev_close = close.iloc[-2] if len(close) > 1 else current_price

    except:
        return {k: 5.0 for k in WEIGHTS.keys()}

    scores = {}
    scores['Momentum']   = score_momentum(crsi)
    scores['Volume']     = score_volume(obv_trend, vol_ratio)
    scores['PriceAction']= score_price_action(current_price, support, prev_close)
    scores['Trend']      = score_trend(current_price, ma20)
    scores['Oscillator'] = score_oscillator(rsi)
    scores['Volatility'] = score_volatility(band_width)

    return scores

# ====================== MULTI TIMEFRAME (15m & 30m) ======================
def calculate_multi_timeframe_score(df_15m, df_30m, current_price, support):
    s15 = calculate_view_scores(df_15m, current_price, support)
    s30 = calculate_view_scores(df_30m, current_price, support)

    fs15 = calculate_weighted_score(s15)
    fs30 = calculate_weighted_score(s30)

    # 15m: 40%, 30m: 60%
    final_score = (fs15 * 0.40) + (fs30 * 0.60)

    return round(final_score, 2), round(fs15, 2), round(fs30, 2)

def calculate_weighted_score(scores_dict):
    weighted = sum(scores_dict.get(v, 5.0) * w for v, w in WEIGHTS.items())

    strong = sum(1 for s in scores_dict.values() if s >= 7.5)
    if strong >= 5: weighted += 1.2
    elif strong >= 4: weighted += 0.8

    if scores_dict.get('Momentum', 0) >= 8.0 and scores_dict.get('Volume', 0) >= 8.0:
        weighted += 1.1

    weak = sum(1 for s in scores_dict.values() if s <= 4.0)
    if weak >= 3: weighted -= 0.9

    return round(min(max(weighted, 3.0), 10.0), 2)

# ====================== LẤY DỮ LIỆU ======================
@st.cache_data(ttl=1800)  # Cache 30 phút
def get_data(symbol, interval="15m", days=30):
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = Vnstock().stock(symbol=symbol).quote.history(start=start, end=end, interval=interval)
        return df
    except:
        return pd.DataFrame()

# ====================== GIAO DIỆN ======================
st.sidebar.header("📌 Danh sách cổ phiếu đã mua")

# Form thêm mới
with st.sidebar.form("add_holding"):
    col1, col2 = st.columns([3, 2])
    with col1:
        symbol = st.text_input("Mã CK", placeholder="VHM").upper()
    with col2:
        buy_price = st.number_input("Giá mua", min_value=0.0, value=100.0, step=0.1)
    if st.form_submit_button("➕ Thêm"):
        if symbol:
            st.session_state.holdings.append({"Mã": symbol, "Giá mua": buy_price})
            save_holdings(st.session_state.holdings)
            st.rerun()

# Hiển thị danh sách hiện tại
st.sidebar.subheader("Danh sách hiện tại")
for i, item in enumerate(st.session_state.holdings):
    col1, col2, col3 = st.sidebar.columns([3, 2, 1])
    with col1:
        st.write(f"**{item['Mã']}** - {item['Giá mua']}")
    with col3:
        if st.button("🗑", key=f"del_{i}"):
            st.session_state.holdings.pop(i)
            save_holdings(st.session_state.holdings)
            st.rerun()

# ====================== QUÉT CẢNH BÁO ======================
if st.button("🚨 Quét cảnh báo ngay", type="primary", use_container_width=True):
    if not st.session_state.holdings:
        st.error("Chưa có cổ phiếu nào")
    else:
        with st.spinner("Đang quét 15m & 30m..."):
            results = []
            for holding in st.session_state.holdings:
                symbol = holding["Mã"]
                buy_price = holding["Giá mua"]

                df_15m = get_data(symbol, "15m", 30)
                df_30m = get_data(symbol, "30m", 30)

                current_price = df_30m['close'].iloc[-1] if not df_30m.empty else buy_price
                support = df_30m['low'].rolling(20).min().iloc[-1] if not df_30m.empty else buy_price * 0.95

                final_score, s15, s30 = calculate_multi_timeframe_score(df_15m, df_30m, current_price, support)

                recommend = "NẮM GIỮ" if final_score >= 7.2 else "BÁN" if final_score <= 5.2 else "THEO DÕI"

                # Gửi Telegram nếu BÁN
                if recommend == "BÁN" and st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    msg = f"🚨 CẢNH BÁO BÁN\nMã: <b>{symbol}</b>\nGiá mua: {buy_price}\nGiá hiện tại: {current_price:.2f}\nFinal Score: {final_score}\n15m: {s15} | 30m: {s30}"
                    requests.get(f"https://api.telegram.org/bot{st.session_state.telegram_token}/sendMessage",
                        params={"chat_id": st.session_state.telegram_chat_id, "text": msg, "parse_mode": "HTML"})

                results.append({
                    "Mã CK": symbol,
                    "Giá mua": buy_price,
                    "Giá hiện tại": round(current_price, 2),
                    "15m": s15,
                    "30m": s30,
                    "Final Score": final_score,
                    "Khuyến nghị": recommend,
                    "Ngành nghề": get_sector(symbol)
                })

            df_result = pd.DataFrame(results)
            st.success(f"✅ Đã quét {len(results)} cổ phiếu")

            st.dataframe(
                df_result.style.background_gradient(subset=['Final Score'], cmap='RdYlGn'),
                use_container_width=True,
                height=650
            )

st.caption("Warning System v3 - Tối ưu cho cảnh báo bán • Auto 30 phút")
