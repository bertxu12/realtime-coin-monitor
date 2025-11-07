import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime
import time
import talib
import platform
import io
import base64

# ←←←←←←←←←←←←←←  1. 填你的 Server酱 SENDKEY  ←←←←←←←←←←←←←
sendkey = "SCT301726T5I3LgC6jJnGMzniFcKnQ0B0S"  # ← 改成你自己的！
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

refresh_interval = 5
st.set_page_config(page_title="实时币价监控", layout="wide")

# 币安监控币种
COINS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "DOGE": "DOGEUSDT"
}

if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=["时间"] + list(COINS.keys()))
if "alert_triggered" not in st.session_state:
    st.session_state.alert_triggered = {k: False for k in COINS.keys()}

# 检查是否本地环境
is_local = platform.system() == "Windows"

# ========================== 获取币价 ==========================
def get_price(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
        data = r.json()
        price = float(data["price"])
        return price
    except:
        return None

def fetch_all_prices():
    prices = {}
    for name, symbol in COINS.items():
        p = get_price(symbol)
        prices[name] = p
    return prices

# ========================== 报警提醒 ==========================
def play_sound():
    """兼容 Streamlit Cloud（Linux）和 Windows 的声音播放"""
    if is_local:
        import winsound
        winsound.Beep(1500, 700)
    else:
        # 生成 beep 音频（440Hz 正弦波）
        import numpy as np
        import soundfile as sf
        sr = 44100
        t = np.linspace(0, 0.3, int(sr * 0.3), endpoint=False)
        wave = 0.5 * np.sin(2 * np.pi * 440 * t)
        buf = io.BytesIO()
        sf.write(buf, wave, sr, format="wav")
        st.audio(buf.getvalue(), format="audio/wav")

def trigger_alert(name, price, target):
    msg = f"{name} 已突破阈值！\n当前价格：${price:,.2f}\n报警线：${target:,.2f}\n时间：{datetime.now().strftime('%H:%M:%S')}"
    play_sound()
    try:
        requests.post(f"https://sctapi.ftqq.com/{sendkey}.send",
                      data={"title": f"{name} 报警", "desp": msg}, timeout=5)
    except:
        pass
    st.warning(msg)

# ========================== 主界面 ==========================
st.title("📊 实时币价监控（币安）")
st.markdown("**支持微信报警 + 声音提醒 + 技术指标分析（SMA / RSI）**")

# 侧边栏参数
st.sidebar.header("⚙️ 报警设置")
alerts = {coin: st.sidebar.number_input(f"{coin} 报警价($)", value=0.0, format="%0.2f", key=f"alert_{coin}")
          for coin in COINS}

st.sidebar.header("📈 技术指标设置")
sma_period = st.sidebar.slider("SMA 周期", 5, 50, 20)
rsi_period = st.sidebar.slider("RSI 周期", 5, 30, 14)

# ========================== 获取数据 ==========================
prices = fetch_all_prices()
now = datetime.now().strftime("%H:%M:%S")
row = {"时间": now, **prices}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([row])], ignore_index=True)

# ========================== 实时表格 ==========================
st.subheader("💰 实时价格表")
table = []
for coin in COINS:
    p = prices.get(coin)
    color = "limegreen" if p else "gray"
    table.append({
        "币种": coin,
        "价格": f"<b style='color:{color};font-size:1.2em'>${p:,.2f}</b>" if p else "-",
        "报警价": f"${alerts[coin]:,.2f}" if alerts[coin] > 0 else "-"
    })
st.markdown(pd.DataFrame(table).to_html(escape=False, index=False), unsafe_allow_html=True)

# ========================== 趋势图 + 技术指标 ==========================
hist = st.session_state.history.copy().tail(200)
for c in COINS:
    hist[c] = pd.to_numeric(hist[c], errors="coerce")

st.subheader("📊 趋势分析")
for coin in COINS:
    with st.expander(f"{coin} 价格走势（SMA{ sma_period } / RSI{ rsi_period }）", expanded=False):
        df = hist[["时间", coin]].dropna()
        if len(df) < rsi_period + 1:
            st.info(f"{coin} 数据不足，无法计算技术指标")
            continue

        df['SMA'] = talib.SMA(df[coin], timeperiod=sma_period)
        df['RSI'] = talib.RSI(df[coin], timeperiod=rsi_period)

        # 绘制
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), gridspec_kw={'height_ratios': [3, 1]})
        ax1.plot(df["时间"], df[coin], label=coin, color='blue')
        ax1.plot(df["时间"], df["SMA"], label=f"SMA {sma_period}", color='orange', linestyle='--')
        ax1.legend(); ax1.grid(alpha=0.3); plt.xticks(rotation=45)
        ax1.set_title(f"{coin} 价格趋势")

        ax2.plot(df["时间"], df["RSI"], color='purple', label='RSI')
        ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
        ax2.legend(); ax2.grid(alpha=0.3); plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

        # RSI 解释
        last_rsi = df['RSI'].iloc[-1]
        if last_rsi > 70:
            st.warning(f"{coin} RSI = {last_rsi:.1f} → 超买信号")
        elif last_rsi < 30:
            st.success(f"{coin} RSI = {last_rsi:.1f} → 超卖信号")
        else:
            st.info(f"{coin} RSI = {last_rsi:.1f} → 中性区间")

# ========================== 报警逻辑 ==========================
for coin in COINS:
    cur = prices.get(coin)
    tar = alerts[coin]
    if cur and tar > 0:
        if cur >= tar and not st.session_state.alert_triggered[coin]:
            trigger_alert(coin, cur, tar)
            st.session_state.alert_triggered[coin] = True
        elif cur < tar:
            st.session_state.alert_triggered[coin] = False

# ========================== 自动刷新 ==========================
st.caption(f"更新时间：{now}　|　每 {refresh_interval}s 自动刷新")
ph = st.empty()
for i in range(refresh_interval, 0, -1):
    ph.info(f"⏳ 实时监控中... {i}s")
    time.sleep(1)
ph.empty()
st.rerun()
