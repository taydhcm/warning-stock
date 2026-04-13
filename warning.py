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

# ====================== LOAD DANH SÁCH TỪ FILE ======================
HOLDINGS_FILE = "list.env"

def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_holdings(holdings):
    with open(HOLDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)

if 'holdings' not in st.session_state:
    st.session_state.holdings = load_holdings()

# ====================== HÀM TÍNH CHỈ BÁO ======================
def calculate_view_scores(df, current_price, support):
    if df is None or df.empty or len(df) < 30:
        return {"PriceAction": 5.0, "Volume": 5.0, "OBV": 5.0}

    try:
        close = df['close']
        volume = df['volume']

        # Price Action
        support_level = df['low'].rolling(20).min().iloc[-1]
        pa_score = 9.0 if current_price > support_level * 1.015 else \
                   4.0 if current_price < support_level * 0.985 else 5.5

        # Volume
        vol_ratio = volume.iloc[-1] / volume.rolling(20).mean().iloc[-1] if len(df) > 20 else 1.0
        vol_score = 9.0 if vol_ratio > 1.4 else 4.0 if vol_ratio < 0.8 else 6.0

        # OBV
        obv = ta.obv(close, volume)
        obv_trend = "up" if obv.diff().iloc[-1] > 0 else "down" if obv.diff().iloc[-1] < 0 else "flat"
        obv_score = 9.0 if obv_trend == "up" else 3.5 if obv_trend == "down" else 5.5

    except:
        pa_score = vol_score = obv_score = 5.0

    return {
        "PriceAction": pa_score,
        "Volume": vol_score,
        "OBV": obv_score
    }

# ====================== TÍNH ĐIỂM TỔNG HỢP ======================
def calculate_warning_score(df_30m, df_1h, current_price, support):
    s30 = calculate_view_scores(df_30m, current_price, support)
    s1h = calculate_view_scores(df_1h,  current_price, support)

    # Trọng số: 30m = 40%, 1h = 60%
    final_score = (s30["PriceAction"] * 0.4 * 0.4) + (s1h["PriceAction"] * 0.6 * 0.4) + \
                  (s30["Volume"] * 0.4 * 0.3) + (s1h["Volume"] * 0.6 * 0.3) + \
                  (s30["OBV"] * 0.4 * 0.3) + (s1h["OBV"] * 0.6 * 0.3)

    final_score = round(final_score, 2)

    # Xác định khuyến nghị theo bảng của bạn
    if current_price < support * 0.985 and s1h["OBV"] <= 4.0:
        recommend = "BÁN KHẨN"
    elif s1h["Volume"] <= 4.0 and s1h["OBV"] <= 4.0:
        recommend = "BÁN"
    elif s1h["OBV"] <= 4.0:
        recommend = "BÁN"
    elif s1h["PriceAction"] >= 8.0 and s1h["Volume"] >= 8.0 and s1h["OBV"] >= 8.0:
        recommend = "NẮM GIỮ"
    else:
        recommend = "THEO DÕI"

    return final_score, recommend, s30, s1h

# ====================== LẤY DỮ LIỆU ======================
@st.cache_data(ttl=1800)  # Cache 30 phút
def get_data(symbol, interval="30m", days=30):
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

# Hiển thị danh sách
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
        with st.spinner("Đang quét 30m & 1h..."):
            results = []
            for holding in st.session_state.holdings:
                symbol = holding["Mã"]
                buy_price = holding["Giá mua"]

                df_30m = get_data(symbol, "30m", 30)
                df_1h  = get_data(symbol, "1h",  60)

                current_price = df_1h['close'].iloc[-1] if not df_1h.empty else buy_price
                support = df_1h['low'].rolling(20).min().iloc[-1] if not df_1h.empty else buy_price * 0.95

                final_score, recommend, s30, s1h = calculate_warning_score(df_30m, df_1h, current_price, support)

                # Gửi Telegram nếu BÁN hoặc BÁN KHẨN
                if recommend in ["BÁN", "BÁN KHẨN"] and st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    msg = f"🚨 CẢNH BÁO {recommend}\nMã: <b>{symbol}</b>\nGiá mua: {buy_price}\nGiá hiện tại: {current_price:.2f}\nFinal Score: {final_score}\n30m: {s30['PriceAction']:.1f}/{s30['Volume']:.1f}/{s30['OBV']:.1f}\n1h: {s1h['PriceAction']:.1f}/{s1h['Volume']:.1f}/{s1h['OBV']:.1f}"
                    try:
                        requests.get(f"https://api.telegram.org/bot{st.session_state.telegram_token}/sendMessage",
                            params={"chat_id": st.session_state.telegram_chat_id, "text": msg, "parse_mode": "HTML"})
                    except:
                        pass

                results.append({
                    "Mã CK": symbol,
                    "Giá mua": buy_price,
                    "Giá hiện tại": round(current_price, 2),
                    "30m": f"{s30['PriceAction']:.1f}/{s30['Volume']:.1f}/{s30['OBV']:.1f}",
                    "1h": f"{s1h['PriceAction']:.1f}/{s1h['Volume']:.1f}/{s1h['OBV']:.1f}",
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

st.caption("Warning System v4 - Tối ưu theo chiến lược Price Action + Volume + OBV • Auto 1 giờ")
