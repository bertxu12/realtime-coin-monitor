import streamlit as st
import pandas as pd
import requests
import datetime
import time
import platform

# ===================== 页面设置 =====================
st.set_page_config(page_title="💹 实时币价监控系统", layout="wide")
st.title("💰 实时加密货币监控系统（微信推送增强版）")
st.markdown("支持：自动接口切换 + 趋势图 + 报警音 + 微信推送")

# ===================== 参数设置 =====================
coins = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

st.sidebar.header("⚙️ 参数配置")
alert_threshold = st.sidebar.number_input("📈 报警阈值（%）", 0.1, 50.0, 2.0)
refresh_interval = st.sidebar.slider("🔄 刷新间隔（秒）", 5, 60, 10)

st.sidebar.header("📱 微信推送配置")
push_method = st.sidebar.selectbox("推送方式", ["关闭", "Server酱", "PushPlus", "Bark"])
push_token = st.sidebar.text_input("推送Token或Key")

# ===================== 数据缓存 =====================
if "history" not in st.session_state:
    st.session_state["history"] = {c: pd.DataFrame(columns=["time", "price"]) for c in coins}
if "last_prices" not in st.session_state:
    st.session_state["last_prices"] = {}

# ===================== API 镜像列表 =====================
API_BASES = [
    "https://api-gcp.binance.com",
    "https://api.binance.us",
    "https://api.binance.com"
]

def get_price(symbol):
    """从多个 Binance 接口获取价格"""
    for base in API_BASES:
        try:
            url = f"{base}/api/v3/ticker/price?symbol={symbol}"
            r = requests.get(url, timeout=5)
            data = r.json()
            if "price" in data:
                return float(data["price"])
        except Exception:
            continue
    return None

# ===================== 报警提示音 =====================
def play_alert():
    if platform.system() == "Windows":
        try:
            import winsound
            winsound.Beep(1200, 400)
        except:
            pass
    else:
        st.balloons()  # 云端动画

# ===================== 微信推送函数 =====================
def send_wechat_push(title, content):
    """支持 Server酱 / PushPlus / Bark 三种推送"""
    if not push_token or push_method == "关闭":
        return
    try:
        if push_method == "Server酱":
            url = f"https://sctapi.ftqq.com/{push_token}.send"
            requests.post(url, data={"title": title, "desp": content})
        elif push_method == "PushPlus":
            url = "https://www.pushplus.plus/send"
            requests.post(url, json={"token": push_token, "title": title, "content": content})
        elif push_method == "Bark":
            url = f"https://api.day.app/{push_token}/{title}/{content}"
            requests.get(url)
    except Exception as e:
        st.warning(f"微信推送失败：{e}")

# ===================== 主展示容器 =====================
placeholder = st.empty()

while True:
    prices, changes = {}, {}
    for coin in coins:
        price = get_price(coin)
        if price:
            prices[coin] = price
            # 保存历史数据
            df = st.session_state["history"][coin]
            new_row = pd.DataFrame({"time": [datetime.datetime.now()], "price": [price]})
            df = pd.concat([df, new_row]).tail(100)
            st.session_state["history"][coin] = df

            last_price = st.session_state["last_prices"].get(coin)
            if last_price:
                change = (price - last_price) / last_price * 100
                changes[coin] = change
                # 报警逻辑
                if abs(change) >= alert_threshold:
                    msg = f"{coin} 当前价 {price:.2f}，涨跌幅 {change:+.2f}%"
                    play_alert()
                    st.toast(f"⚠️ {msg}")
                    send_wechat_push(f"{coin} 价格波动报警", msg)
            st.session_state["last_prices"][coin] = price

    # ===================== 展示表格 =====================
    with placeholder.container():
        if prices:
            df_display = pd.DataFrame({
                "币种": prices.keys(),
                "当前价 (USDT)": [f"{v:.2f}" for v in prices.values()],
                "涨跌幅 (%)": [f"{changes.get(c, 0):+.2f}" for c in prices.keys()],
                "趋势": [
                    "📈 上涨" if changes.get(c, 0) > 0 else ("📉 下跌" if changes.get(c, 0) < 0 else "⏸ 持平")
                    for c in prices.keys()
                ]
            })
            st.subheader("💹 实时行情")
            st.dataframe(df_display, use_container_width=True)

            st.subheader("📊 趋势分析")
            cols = st.columns(len(coins))
            for i, coin in enumerate(coins):
                with cols[i]:
                    hist = st.session_state["history"][coin]
                    if len(hist) > 2:
                        st.line_chart(hist.set_index("time")["price"], height=250)
                    else:
                        st.info(f"⏳ {coin} 数据收集中...")
        else:
            st.error("🚫 无法获取任何币价，请检查网络或接口。")

    time.sleep(refresh_interval)
