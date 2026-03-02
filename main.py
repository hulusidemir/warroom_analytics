import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from logic.data_feed import DataFeed
from logic.indicators import QuantLogic
import time
import datetime

# --- LANGUAGE SETTINGS ---
if 'language' not in st.session_state:
    st.session_state['language'] = 'tr'

TRANSLATIONS = {
    "en": {
        "config": "⚙️ CONFIGURATION",
        "ticker": "TICKER",
        "select_ticker": "--- SELECT ---",
        "select_msg": "👈 Please select a ticker from the sidebar to initialize the War Room.",
        "timeframe": "TIMEFRAME",
        "refresh": "REFRESH (sec)",
        "force_refresh": "FORCE REFRESH",
        "logs": "📡 LOGS",
        "analyzing": "Analyzing...",
        "init_protocol": "Initializing War Room Protocol...",
        "accessing_feeds": "Accessing Exchange Feeds...",
        "fetch_fail": "Failed to fetch data. Check ticker or API connection.",
        "regime": "REGIME",
        "pattern": "PATTERN",
        "detected_signals": "### ⚠️ DETECTED SIGNALS",
        "price": "PRICE",
        "open_interest": "OPEN INTEREST",
        "funding_rates": "FUNDING RATES",
        "btc_price": "BTC PRICE",
        "market_data": "MARKET DATA",
        "rank": "Rank",
        "mcap": "M. Cap",
        "ath_atl": "ATH / ATL",
        "profile": "PROFILE",
        "view_desc": "▶ View Asset Description",
        "market_regime": "### 🛡️ MARKET REGIME",
        "quant_analysis": "### 🧠 QUANTITATIVE ANALYSIS",
        "signal_matrix": "SIGNAL MATRIX",
        "price_action": "PRICE ACTION + VWAP",
        "cvd": "CUMULATIVE VOLUME DELTA (CVD)",
        "oi": "OPEN INTEREST (OI)",
        "regime_long_buildup": "Long Buildup 🟢",
        "regime_short_covering": "Short Covering 👻",
        "regime_short_buildup": "Short Buildup 🔴",
        "regime_long_liq": "Long Liq 🩸",
        "regime_strong_long_buildup": "Strong Long Buildup 🟢🔥",
        "regime_absorption_long_buildup": "Absorption Long Buildup 🟢🛡️",
        "regime_short_covering_agg": "Short Covering 👻🔥",
        "regime_short_covering_pass": "Passive Short Covering 👻🛡️",
        "regime_strong_short_buildup": "Strong Short Buildup 🔴🔥",
        "regime_absorption_short_buildup": "Absorption Short Buildup 🔴🛡️",
        "regime_long_liq_agg": "Long Liquidation 🩸🔥",
        "regime_long_liq_pass": "Passive Long Liquidation 🩸🛡️",
        "regime_neutral": "Neutral",
        "regime_strong_long_buildup_desc": "Aggressive buyers are entering, driving price up. Healthy uptrend. (Price ⬆️, OI ⬆️, CVD ⬆️)",
        "regime_absorption_long_buildup_desc": "Aggressive sellers are present (CVD down), but passive buyers (limit orders) are absorbing the selling pressure. Hidden bullish signal. (Price ⬆️, OI ⬆️, CVD ⬇️)",
        "regime_short_covering_agg_desc": "Short positions are closing via aggressive market buy orders. (Price ⬆️, OI ⬇️, CVD ⬆️)",
        "regime_short_covering_pass_desc": "Short positions are closing via limit orders, or price is rising despite aggressive selling. (Price ⬆️, OI ⬇️, CVD ⬇️)",
        "regime_strong_short_buildup_desc": "Aggressive sellers are entering, driving price down. Healthy downtrend. (Price ⬇️, OI ⬆️, CVD ⬇️)",
        "regime_absorption_short_buildup_desc": "Aggressive buyers are present, but passive sellers (walls) are absorbing the buying pressure. (Price ⬇️, OI ⬆️, CVD ⬆️)",
        "regime_long_liq_agg_desc": "Long positions are closing via aggressive sells or stop-losses being triggered. (Price ⬇️, OI ⬇️, CVD ⬇️)",
        "regime_long_liq_pass_desc": "Longs are closing, but there is also aggressive buying (or closing via limit sells). (Price ⬇️, OI ⬇️, CVD ⬆️)",
        "regime_neutral_desc": "No clear trend or significant order flow imbalance detected.",
        "sfp_bullish": "Bullish SFP 🚀",
        "sfp_bearish": "Bearish SFP 🔻",
        "none": "None",
        "cvd_est_warn": "⚠️ CVD is ESTIMATED (Real Taker data unavailable for this exchange/symbol)."
    },
    "tr": {
        "config": "⚙️ AYARLAR",
        "ticker": "SEMBOL",
        "select_ticker": "--- SEÇİNİZ ---",
        "select_msg": "👈 War Room'u başlatmak için lütfen sol menüden bir sembol seçin.",
        "timeframe": "ZAMAN DİLİMİ",
        "refresh": "YENİLEME (sn)",
        "force_refresh": "ZORLA YENİLE",
        "logs": "📡 KAYITLAR",
        "analyzing": "Analiz ediliyor...",
        "init_protocol": "War Room Protokolü Başlatılıyor...",
        "accessing_feeds": "Borsa Verilerine Erişiliyor...",
        "fetch_fail": "Veri alınamadı. Sembolü veya API bağlantısını kontrol edin.",
        "regime": "REJİM",
        "pattern": "FORMASYON",
        "detected_signals": "### ⚠️ TESPİT EDİLEN SİNYALLER",
        "price": "FİYAT",
        "open_interest": "AÇIK POZİSYON (OI)",
        "funding_rates": "FONLAMA ORANLARI",
        "btc_price": "BTC FİYATI",
        "market_data": "PİYASA VERİLERİ",
        "rank": "Sıra",
        "mcap": "Piyasa Değeri",
        "ath_atl": "EN YÜKSEK / EN DÜŞÜK",
        "profile": "PROFİL",
        "view_desc": "▶ Varlık Açıklamasını Görüntüle",
        "market_regime": "### 🛡️ PİYASA REJİMİ",
        "quant_analysis": "### 🧠 KANTİTATİF ANALİZ",
        "signal_matrix": "SİNYAL MATRİSİ",
        "price_action": "FİYAT HAREKETİ + VWAP",
        "cvd": "KÜMÜLATİF HACİM DELTASI (CVD)",
        "oi": "AÇIK POZİSYON (OI)",
        "regime_long_buildup": "Long Toplama 🟢",
        "regime_short_covering": "Short Kapama 👻",
        "regime_short_buildup": "Short Toplama 🔴",
        "regime_long_liq": "Long Tasfiye 🩸",
        "regime_strong_long_buildup": "Güçlü Long Toplama 🟢🔥",
        "regime_absorption_long_buildup": "Absorbe Long Toplama 🟢🛡️",
        "regime_short_covering_agg": "Short Kapama 👻🔥",
        "regime_short_covering_pass": "Pasif Short Kapama 👻🛡️",
        "regime_strong_short_buildup": "Güçlü Short Toplama 🔴🔥",
        "regime_absorption_short_buildup": "Absorbe Short Toplama 🔴🛡️",
        "regime_long_liq_agg": "Long Tasfiye 🩸🔥",
        "regime_long_liq_pass": "Pasif Long Tasfiye 🩸🛡️",
        "regime_neutral": "Nötr",
        "regime_strong_long_buildup_desc": "Agresif alıcılar piyasaya giriyor ve fiyatı yukarı sürüyor. En sağlıklı yükseliş sinyali. (Fiyat ⬆️, OI ⬆️, CVD ⬆️)",
        "regime_absorption_long_buildup_desc": "Agresif satıcılar var (CVD düşüyor) ama pasif alıcılar (limit emirler) bu satışı karşılıyor. Gizli bir boğa sinyali. (Fiyat ⬆️, OI ⬆️, CVD ⬇️)",
        "regime_short_covering_agg_desc": "Short pozisyonlar agresif market buy emirleriyle kapatılıyor. (Fiyat ⬆️, OI ⬇️, CVD ⬆️)",
        "regime_short_covering_pass_desc": "Short pozisyonlar limit emirlerle kapatılıyor veya agresif satışa rağmen fiyat yükseliyor. (Fiyat ⬆️, OI ⬇️, CVD ⬇️)",
        "regime_strong_short_buildup_desc": "Agresif satıcılar piyasaya giriyor ve fiyatı aşağı baskılıyor. En sağlıklı düşüş sinyali. (Fiyat ⬇️, OI ⬆️, CVD ⬇️)",
        "regime_absorption_short_buildup_desc": "Agresif alıcılar var ama pasif satıcılar (duvarlar) bu alışı karşılıyor ve fiyat düşüyor. (Fiyat ⬇️, OI ⬆️, CVD ⬆️)",
        "regime_long_liq_agg_desc": "Long pozisyonlar agresif satışlarla veya stop patlatarak kapanıyor. (Fiyat ⬇️, OI ⬇️, CVD ⬇️)",
        "regime_long_liq_pass_desc": "Longlar kapanıyor ama agresif alımlar da var (veya limit satışlarla kapanış). (Fiyat ⬇️, OI ⬇️, CVD ⬆️)",
        "regime_neutral_desc": "Belirgin bir trend veya emir akışı dengesizliği tespit edilemedi.",
        "sfp_bullish": "Boğa SFP 🚀",
        "sfp_bearish": "Ayı SFP 🔻",
        "none": "Yok",
        "cvd_est_warn": "⚠️ CVD TAHMİNİDİR (Bu borsa/sembol için gerçek Taker verisi alınamadı)."
    }
}

def t(key):
    return TRANSLATIONS[st.session_state['language']].get(key, key)

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="WAR ROOM: HFT ANALYTICS",
    page_icon="☠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for that "Terminal" feel
st.markdown("""
    <style>
    .stApp {background-color: #0e1117;}
    .metric-card {background-color: #161b22; padding: 10px; border-radius: 5px; border: 1px solid #30363d;}
    h1, h2, h3 {color: #e6edf3;}
    /* Cursor Hand for Selectbox */
    div[data-baseweb="select"] > div {
        cursor: pointer !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZATION ---
@st.cache_resource
def get_feed():
    return DataFeed()

feed = get_feed()
logic = QuantLogic()

# --- SIDEBAR CONTROL ---
st.sidebar.markdown("""
    <div style="text-align: center; padding: 15px; background-color: #161b22; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 25px;">
        <h1 style="color: #e6edf3; margin: 0; font-size: 22px; font-family: 'Courier New', monospace;">WAR ROOM</h1>
        <div style="height: 2px; background: linear-gradient(90deg, #00e5ff, #ff00ff); margin: 10px auto; width: 100%;"></div>
        <p style="color: #8b949e; font-size: 10px; margin: 0; letter-spacing: 3px; font-weight: bold;">QUANTITATIVE TERMINAL</p>
        <p style="color: #e6edf3; font-size: 11px; margin-top: 8px; font-family: 'Courier New', monospace; font-weight: bold; text-shadow: 0 0 4px rgba(0, 229, 255, 0.6);">by Hulusi DEMİR</p>
        <p style="color: #30363d; font-size: 9px; margin-top: 5px;">v1.1.0</p>
    </div>
    """, unsafe_allow_html=True)

# Language Selection
c1, c2 = st.sidebar.columns(2)
if c1.button("🇺🇸 EN", use_container_width=True):
    st.session_state['language'] = 'en'
    st.rerun()
if c2.button("🇹🇷 TR", use_container_width=True):
    st.session_state['language'] = 'tr'
    st.rerun()

st.sidebar.markdown(f"### {t('config')}")
available_symbols = feed.get_symbols()
if not available_symbols:
    available_symbols = ["BTC/USDT"]

# Create a mapping for display (Show only Base Asset, e.g., BTC, ETH, SOL)
# available_symbols is already sorted by Volume from get_symbols()
symbol_map = {s.split('/')[0]: s for s in available_symbols}
display_options = list(symbol_map.keys())
# display_options.sort() # Removed to preserve Volume ranking

# Add placeholder to the beginning
display_options.insert(0, t('select_ticker'))

selected_display = st.sidebar.selectbox(t('ticker'), display_options, index=0, key="symbol_selector")

if selected_display == t('select_ticker'):
    st.info(t('select_msg'))
    # Clear any existing placeholders if necessary or just stop
    st.stop()

# Resolve back to full symbol
symbol = symbol_map[selected_display]

timeframe = st.sidebar.selectbox(t('timeframe'), ["5m", "15m", "1h", "4h"], index=1)
refresh_rate = st.sidebar.slider(t('refresh'), 10, 60, 60)

# Indicator Toggles
st.sidebar.markdown("### 📈 INDICATORS")
show_bb = st.sidebar.checkbox("Bollinger Bands", value=False)
show_ichimoku = st.sidebar.checkbox("Ichimoku Cloud", value=False)
show_psar = st.sidebar.checkbox("Parabolic SAR", value=False)

if st.sidebar.button(t('force_refresh'), use_container_width=True):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader(t('logs'))

# Placeholders for immediate clearing of old data
regime_container = st.sidebar.empty()
sfp_container = st.sidebar.empty()
signals_title_container = st.sidebar.empty()
signals_container = st.sidebar.empty()

# Clear/Loading state
regime_container.info(t('analyzing'))
sfp_container.empty()
signals_title_container.empty()
signals_container.empty()

# --- MAIN DASHBOARD CONTAINER ---
dashboard = st.empty()
dashboard.info(t('init_protocol'))

# --- MAIN DATA FETCH ---
with st.spinner(t('accessing_feeds')):
    df, funding_data = feed.fetch_market_data(symbol, timeframe)
    macro_data = feed.get_macro_context(timeframe)

if df.empty:
    st.error(t('fetch_fail'))
    st.stop()

# --- RENDER DASHBOARD ---
with dashboard.container():
    # --- PROCESSING ---
    df = logic.calculate_vwap(df)
    df = logic.calculate_cvd(df)
    df = logic.identify_oi_regime(df)
    df = logic.detect_sfp(df)
    # New Technical Indicators
    df = logic.calculate_rsi(df)
    df = logic.calculate_mfi(df)
    df = logic.calculate_cmf(df)
    df = logic.calculate_obv(df)
    df = logic.calculate_bollinger_bands(df)
    df = logic.calculate_macd(df)
    df = logic.calculate_stoch_rsi(df)
    
    if show_ichimoku:
        df = logic.calculate_ichimoku(df)
    if show_psar:
        df = logic.calculate_parabolic_sar(df)

    # Generate Technical Summary
    tech_summary = logic.generate_technical_summary(df)

    # Current Candle Stats
    last_close = df['close'].iloc[-1]
    last_open = df['open'].iloc[-1]
    
    # Translate Regime and SFP
    raw_regime = df['regime'].iloc[-1]
    raw_sfp = df['sfp_signal'].iloc[-1] if df['sfp_signal'].iloc[-1] else "None"
    
    regime_map = {
        'Strong Long Buildup 🟢🔥': 'regime_strong_long_buildup',
        'Absorption Long Buildup 🟢🛡️': 'regime_absorption_long_buildup',
        'Short Covering 👻🔥': 'regime_short_covering_agg',
        'Passive Short Covering 👻🛡️': 'regime_short_covering_pass',
        'Strong Short Buildup 🔴🔥': 'regime_strong_short_buildup',
        'Absorption Short Buildup 🔴🛡️': 'regime_absorption_short_buildup',
        'Long Liquidation 🩸🔥': 'regime_long_liq_agg',
        'Passive Long Liquidation 🩸🛡️': 'regime_long_liq_pass',
        'Neutral': 'regime_neutral'
    }
    sfp_map = {
        'Bullish SFP 🚀': 'sfp_bullish',
        'Bearish SFP 🔻': 'sfp_bearish',
        'None': 'none'
    }
    
    regime_key = regime_map.get(raw_regime, 'regime_neutral')
    last_regime = t(regime_key)
    regime_desc = t(f"{regime_key}_desc")
    
    last_sfp = t(sfp_map.get(raw_sfp, 'none'))

    # --- SIDEBAR LOGS UPDATE ---
    regime_container.info(f"{t('regime')}: {last_regime}")
    if raw_sfp != "None":
        sfp_container.warning(f"{t('pattern')}: {last_sfp}")
    else:
        sfp_container.empty()

    # Display Signals in Sidebar
    if tech_summary['signals']:
        signals_title_container.markdown(t('detected_signals'))
        
        # Build the HTML string for all signals
        signals_html = ""
        for sig in tech_summary['signals']:
            if "Bullish" in sig or "Positive" in sig or "Oversold" in sig:
                signals_html += f"""
                    <div style="background-color: rgba(0, 255, 0, 0.2); border: 1px solid #00ff00; padding: 10px; border-radius: 5px; margin-bottom: 5px; color: #e6edf3;">
                        {sig}
                    </div>
                """
            elif "Bearish" in sig or "Negative" in sig or "Overbought" in sig:
                signals_html += f"""
                    <div style="background-color: rgba(255, 0, 0, 0.2); border: 1px solid #ff4444; padding: 10px; border-radius: 5px; margin-bottom: 5px; color: #e6edf3;">
                        {sig}
                    </div>
                """
            else:
                signals_html += f"""
                    <div style="background-color: rgba(128, 128, 128, 0.2); border: 1px solid #8b949e; padding: 10px; border-radius: 5px; margin-bottom: 5px; color: #e6edf3;">
                        {sig}
                    </div>
                """
        
        signals_container.markdown(signals_html, unsafe_allow_html=True)
    else:
        signals_title_container.empty()
        signals_container.empty()

    # OI Stats (Binance)
    last_oi = df['oi'].iloc[-1]
    prev_oi = df['oi'].iloc[-2] if len(df) > 1 else last_oi
    oi_delta_pct = ((last_oi - prev_oi) / prev_oi) * 100 if prev_oi != 0 else 0

    # OI Stats (Bybit)
    last_oi_bybit = df['oi_bybit'].iloc[-1] if 'oi_bybit' in df.columns else 0
    prev_oi_bybit = df['oi_bybit'].iloc[-2] if 'oi_bybit' in df.columns and len(df) > 1 else last_oi_bybit
    oi_bybit_delta_pct = ((last_oi_bybit - prev_oi_bybit) / prev_oi_bybit) * 100 if prev_oi_bybit != 0 else 0

    # Parse Funding Data
    binance_data = funding_data.get('binance', {})
    binance_funding = binance_data.get('fundingRate', 0)
    binance_next_funding_ts = binance_data.get('fundingTimestamp')

    bybit_data = funding_data.get('bybit', {})
    bybit_funding = bybit_data.get('fundingRate', 0)
    bybit_next_funding_ts = bybit_data.get('fundingTimestamp')

    # Calculate Countdown
    def get_countdown(ts):
        if not ts: return "N/A"
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000
        diff = ts - now
        if diff > 0:
            hours = int(diff // (1000 * 60 * 60))
            minutes = int((diff % (1000 * 60 * 60)) // (1000 * 60))
            return f"{hours}h {minutes}m"
        return "0h 0m"

    binance_countdown = get_countdown(binance_next_funding_ts)
    bybit_countdown = get_countdown(bybit_next_funding_ts)

    # --- DASHBOARD HEADER ---
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        # Custom Price Card
        price_delta = last_close - last_open
        price_color = "#00ff00" if price_delta >= 0 else "#ff0000"
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #8b949e; font-size: 0.8rem;">{t('price')}</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #e6edf3;">
                ${last_close:,.2f}
            </div>
            <div style="color: {price_color}; font-size: 0.9rem;">
                {price_delta:+.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        # Custom OI Card
        bin_color = "#00ff00" if oi_delta_pct >= 0 else "#ff0000"
        byb_color = "#00ff00" if oi_bybit_delta_pct >= 0 else "#ff0000"
        
        st.markdown(f"""
    <div class="metric-card">
    <div style="color: #8b949e; font-size: 0.8rem;">{t('open_interest')}</div>
    <div style="margin-top: 5px;">
    <div style="margin-bottom: 2px;"><span style="color: #e6edf3; font-weight: 600;">Binance:</span> ${int(last_oi):,} <span style="color: {bin_color}; font-size: 0.8rem;">({oi_delta_pct:+.2f}%)</span></div>
    <div><span style="color: #e6edf3; font-weight: 600;">Bybit:</span> ${int(last_oi_bybit):,} <span style="color: {byb_color}; font-size: 0.8rem;">({oi_bybit_delta_pct:+.2f}%)</span></div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    with c3:
        # Custom Funding Card
        bin_f_color = "#00ff00" if binance_funding >= 0 else "#ff0000"
        byb_f_color = "#00ff00" if bybit_funding >= 0 else "#ff0000"

        st.markdown(f"""
    <div class="metric-card">
    <div style="color: #8b949e; font-size: 0.8rem;">{t('funding_rates')}</div>
    <div style="margin-top: 5px;">
    <div style="margin-bottom: 2px;">
    <span style="color: #e6edf3; font-weight: 600;">Binance:</span> <span style="color: {bin_f_color}">{binance_funding * 100:.4f}%</span> <span style="color: #8b949e; font-size: 0.8rem;">({binance_countdown})</span>
    </div>
    <div>
    <span style="color: #e6edf3; font-weight: 600;">Bybit:</span> <span style="color: {byb_f_color}">{bybit_funding * 100:.4f}%</span> <span style="color: #8b949e; font-size: 0.8rem;">({bybit_countdown})</span>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    with c4:
        # Custom BTC Macro Card
        btc_price = macro_data.get('price', 0)
        btc_change = macro_data.get('change', 0)
        
        btc_d = macro_data.get('btc_d', 0)
        eth_d = macro_data.get('eth_d', 0)
        usdt_d = macro_data.get('usdt_d', 0)
        
        btc_color = "#00ff00" if btc_change >= 0 else "#ff0000"
        
        st.markdown(f"""
    <div class="metric-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
            <div>
                <div style="color: #8b949e; font-size: 0.8rem;">{t('btc_price')}</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #e6edf3;">${btc_price:,.0f}</div>
                <div style="color: {btc_color}; font-size: 0.8rem;">{btc_change:+.2f}%</div>
            </div>
            <div style="text-align: right;">
                <div style="color: #8b949e; font-size: 0.7rem;">DOMINANCE</div>
                <div style="font-size: 0.8rem; color: #e6edf3;"><span style="color: #f7931a; font-weight: bold;">BTC.D:</span> {btc_d:.1f}%</div>
                <div style="font-size: 0.8rem; color: #e6edf3;"><span style="color: #627eea; font-weight: bold;">ETH.D:</span> {eth_d:.1f}%</div>
                <div style="font-size: 0.8rem; color: #e6edf3;"><span style="color: #26a17b; font-weight: bold;">USDT.D:</span> {usdt_d:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- FUNDAMENTAL INTELLIGENCE (REMOVED) ---
    fund_data = None

    if fund_data:
        st.markdown("---")
        f1, f2, f3 = st.columns([1, 1, 2])
        
        market_data = fund_data.get('market_data', {})
        rank = fund_data.get('market_cap_rank', 'N/A')
        mcap = market_data.get('market_cap', {}).get('usd', 0)
        
        ath = market_data.get('ath', {}).get('usd', 0)
        ath_change = market_data.get('ath_change_percentage', {}).get('usd', 0)
        try:
            ath_date_raw = market_data.get('ath_date', {}).get('usd', '')[:10]
            ath_date = datetime.datetime.strptime(ath_date_raw, "%Y-%m-%d").strftime("%d/%m/%Y") if ath_date_raw else ""
        except:
            ath_date = ""
        
        atl = market_data.get('atl', {}).get('usd', 0)
        atl_change = market_data.get('atl_change_percentage', {}).get('usd', 0)
        try:
            atl_date_raw = market_data.get('atl_date', {}).get('usd', '')[:10]
            atl_date = datetime.datetime.strptime(atl_date_raw, "%Y-%m-%d").strftime("%d/%m/%Y") if atl_date_raw else ""
        except:
            atl_date = ""
        
        categories = ", ".join(fund_data.get('categories', [])[:3])
        
        import re
        raw_desc = fund_data.get('description', {}).get('en', '')
        clean_desc = re.sub('<[^<]+?>', '', raw_desc) if raw_desc else "No description available."
        
        with f1:
            st.markdown(f"""
    <div class="metric-card">
    <div style="color: #8b949e; font-size: 0.8rem;">{t('market_data')}</div>
    <div style="margin-top: 5px;">
    <div style="margin-bottom: 2px;"><span style="color: #e6edf3; font-weight: 600;">{t('rank')}:</span> #{rank}</div>
    <div><span style="color: #e6edf3; font-weight: 600;">{t('mcap')}:</span> ${mcap:,.0f}</div>
    </div>
    </div>
    """, unsafe_allow_html=True)
            
        with f2:
            st.markdown(f"""
    <div class="metric-card">
    <div style="color: #8b949e; font-size: 0.8rem;">{t('ath_atl')}</div>
    <div style="margin-top: 5px;">
    <div style="margin-bottom: 4px;">
    <span style="color: #ff4444; font-weight: 600;">ATH:</span> ${ath:,.2f} <span style="font-size: 0.8rem;">({ath_change:.1f}%)</span> <span style="font-size: 0.7rem; color: #6e7681;">{ath_date}</span>
    </div>
    <div>
    <span style="color: #00ff00; font-weight: 600;">ATL:</span> ${atl:,.2f} <span style="font-size: 0.8rem;">({atl_change:.1f}%)</span> <span style="font-size: 0.7rem; color: #6e7681;">{atl_date}</span>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
            
        with f3:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #8b949e; font-size: 0.8rem;">{t('profile')}: {fund_data.get('name')}</div>
                <div style="margin-top: 5px; font-size: 0.9rem; color: #e6edf3;">
                    <span style="color: #00e5ff;">{categories}</span>
                </div>
                <div style="margin-top: 8px; border-top: 1px solid #30363d; padding-top: 8px;">
                    <details>
                        <summary style="color: #8b949e; font-size: 0.8rem; cursor: pointer; outline: none; user-select: none;">
                            <span style="border-bottom: 1px dashed #8b949e;">{t('view_desc')}</span>
                        </summary>
                        <div style="margin-top: 10px; font-size: 0.85rem; color: #c9d1d9; line-height: 1.6; max-height: 250px; overflow-y: auto; padding-right: 5px; text-align: justify;">
                            {clean_desc}
                        </div>
                    </details>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Market Regime Row
    st.markdown(f"{t('market_regime')}: {last_regime}", help=regime_desc)

    # CVD Estimation Warning
    if df['is_cvd_estimated'].iloc[-1]:
        st.warning(t('cvd_est_warn'))

    # --- WAR ROOM CHARTS ---
    # We use Plotly Subplots: Main Price, CVD, OI
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{symbol} {t('price_action')}", t('cvd'), t('oi'))
    )

    # 1. Price Chart (Candles)
    fig.add_trace(go.Candlestick(
        x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='Price'
    ), row=1, col=1)

    # VWAP Overlay
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['vwap'], mode='lines', name='VWAP', line=dict(color='orange', width=1)
    ), row=1, col=1)

    # Bollinger Bands
    if show_bb:
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['bb_upper'], mode='lines', name='BB Upper', line=dict(color='gray', width=1, dash='dash')
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['bb_lower'], mode='lines', name='BB Lower', line=dict(color='gray', width=1, dash='dash'),
            fill='tonexty'
        ), row=1, col=1)

    # Ichimoku Cloud
    if show_ichimoku:
        # Tenkan & Kijun
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['tenkan_sen'], mode='lines', name='Tenkan-sen', line=dict(color='#0496ff', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['kijun_sen'], mode='lines', name='Kijun-sen', line=dict(color='#991515', width=1)), row=1, col=1)
        
        # Cloud (Senkou A & B) - We need to fill between them. 
        # Plotly fills to the next y trace, so order matters or use fill='tonexty'
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_span_a'], mode='lines', name='Senkou A', 
            line=dict(color='rgba(0, 255, 0, 0.3)', width=0), showlegend=False
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_span_b'], mode='lines', name='Cloud', 
            line=dict(color='rgba(255, 0, 0, 0.3)', width=0), 
            fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)' # Generic fill, color depends on A vs B usually but simple fill here
        ), row=1, col=1)
        
        # Chikou Span
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['chikou_span'], mode='lines', name='Chikou Span', line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dot')), row=1, col=1)

    # Parabolic SAR
    if show_psar:
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['psar'], mode='markers', name='Parabolic SAR',
            marker=dict(color='white', size=2)
        ), row=1, col=1)

    # SFP Markers
    sfp_data = df[df['sfp_signal'].notna()]
    if not sfp_data.empty:
        # Bullish SFP
        bull_sfp = sfp_data[sfp_data['sfp_signal'] == 'Bullish SFP 🚀']
        if not bull_sfp.empty:
            fig.add_trace(go.Scatter(
                x=bull_sfp['timestamp'], y=bull_sfp['low'], mode='markers', name='Bullish SFP',
                marker=dict(symbol='triangle-up', size=10, color='green')
            ), row=1, col=1)
        
        # Bearish SFP
        bear_sfp = sfp_data[sfp_data['sfp_signal'] == 'Bearish SFP 🔻']
        if not bear_sfp.empty:
            fig.add_trace(go.Scatter(
                x=bear_sfp['timestamp'], y=bear_sfp['high'], mode='markers', name='Bearish SFP',
                marker=dict(symbol='triangle-down', size=10, color='red')
            ), row=1, col=1)

    # 2. CVD Chart
    colors = ['green' if val >= 0 else 'red' for val in df['cvd']]
    fig.add_trace(go.Bar(
        x=df['timestamp'], y=df['cvd'], name='CVD', marker_color=colors
    ), row=2, col=1)

    # 3. OI Chart
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['oi'], mode='lines', name='Open Interest', line=dict(color='cyan', width=2)
    ), row=3, col=1)

    # Layout Updates
    fig.update_layout(
        height=800,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- TECHNICAL SUMMARY ---
    st.markdown(t('quant_analysis'))
    t1, t2 = st.columns(2)

    with t1:
        # Calculate percentages for bars
        rsi_val = df['rsi'].iloc[-1]
        mfi_val = df['mfi'].iloc[-1]
        cmf_val = df['cmf'].iloc[-1]
        macd_val = df['macd'].iloc[-1]

        # RSI & MFI (0-100)
        rsi_pct = max(0, min(100, rsi_val))
        mfi_pct = max(0, min(100, mfi_val))

        # CMF (Normalize -0.5 to 0.5 approx, or use min/max)
        cmf_min, cmf_max = df['cmf'].min(), df['cmf'].max()
        if cmf_max - cmf_min == 0: cmf_pct = 50
        else: cmf_pct = ((cmf_val - cmf_min) / (cmf_max - cmf_min)) * 100
        cmf_pct = max(0, min(100, cmf_pct))

        # MACD (Normalize)
        macd_min, macd_max = df['macd'].min(), df['macd'].max()
        if macd_max - macd_min == 0: macd_pct = 50
        else: macd_pct = ((macd_val - macd_min) / (macd_max - macd_min)) * 100
        macd_pct = max(0, min(100, macd_pct))

        # Helper for bar color
        def get_bar_color(val, type='rsi'):
            if type == 'rsi':
                return '#ff4444' if val > 70 or val < 30 else '#00e5ff'
            if type == 'cmf':
                return '#00ff00' if val > 0 else '#ff4444'
            return '#00e5ff'

        st.markdown(f"""
    <div class="metric-card">
    <h4 style="margin-bottom: 15px;">{t('signal_matrix')}</h4>
    <!-- RSI -->
    <div style="margin-bottom: 10px;">
    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8b949e; margin-bottom: 2px;">
    <span>RSI</span>
    <span>{rsi_val:.2f}</span>
    </div>
    <div style="background-color: #30363d; width: 100%; height: 6px; border-radius: 3px;">
    <div style="background-color: {get_bar_color(rsi_val, 'rsi')}; width: {rsi_pct}%; height: 100%; border-radius: 3px;"></div>
    </div>
    </div>
    <!-- MFI -->
    <div style="margin-bottom: 10px;">
    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8b949e; margin-bottom: 2px;">
    <span>MFI</span>
    <span>{mfi_val:.2f}</span>
    </div>
    <div style="background-color: #30363d; width: 100%; height: 6px; border-radius: 3px;">
    <div style="background-color: #00e5ff; width: {mfi_pct}%; height: 100%; border-radius: 3px;"></div>
    </div>
    </div>
    <!-- CMF -->
    <div style="margin-bottom: 10px;">
    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8b949e; margin-bottom: 2px;">
    <span>CMF</span>
    <span>{cmf_val:.2f}</span>
    </div>
    <div style="background-color: #30363d; width: 100%; height: 6px; border-radius: 3px;">
    <div style="background-color: {get_bar_color(cmf_val, 'cmf')}; width: {cmf_pct}%; height: 100%; border-radius: 3px;"></div>
    </div>
    </div>
    <!-- MACD -->
    <div style="margin-bottom: 5px;">
    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8b949e; margin-bottom: 2px;">
    <span>MACD</span>
    <span>{macd_val:.2f}</span>
    </div>
    <div style="background-color: #30363d; width: 100%; height: 6px; border-radius: 3px;">
    <div style="background-color: #e6edf3; width: {macd_pct}%; height: 100%; border-radius: 3px;"></div>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    with t2:
        # Parse the dictionary for a cleaner UI
        sentiment = tech_summary.get('sentiment', 'N/A')
        score = tech_summary.get('score', 0)
        signals = tech_summary.get('signals', [])
        color_map = {
            "green": "#00ff00",
            "lightgreen": "#90ee90",
            "red": "#ff0000",
            "salmon": "#fa8072",
            "gray": "#8b949e"
        }
        raw_color = tech_summary.get('color', 'gray')
        text_color = color_map.get(raw_color, "#e6edf3")
        
        signals_html = "".join([f"<div style='margin-bottom: 4px;'>• {s}</div>" for s in signals])
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.1rem; font-weight: 700; color: {text_color}; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px;">
                {sentiment} <span style="font-size: 0.8rem; color: #8b949e;">(Score: {score})</span>
            </div>
            <div style="font-size: 0.85rem; color: #e6edf3;">
                {signals_html}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Auto-refresh
time.sleep(refresh_rate)
st.rerun()
