import ccxt
import pandas as pd
import streamlit as st
import requests

@st.cache_data(ttl=86400)
def get_all_coins_list_v2():
    """Fetches the full list of coins from CoinGecko (Cached for 24h)."""
    # DEPRECATED: CoinGecko removed.
    return []

@st.cache_data(ttl=3600)
def fetch_symbols_sorted_by_volume(proxies=None):
    """Fetches and sorts symbols by volume, cached for 1 hour."""
    try:
        exchange = ccxt.binanceusdm({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
            'proxies': proxies or {}
        })
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        symbol_vol_list = []
        for symbol, ticker in tickers.items():
            if symbol not in exchange.markets: continue
            market = exchange.markets[symbol]
            if not market.get('active', True): continue
            if market.get('quote') != 'USDT': continue
            if not market.get('swap'): continue
            
            vol = ticker.get('quoteVolume', 0)
            if vol is None: vol = 0
            symbol_vol_list.append((symbol, vol))
            
        symbol_vol_list.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in symbol_vol_list]
    except Exception as e:
        return []

class DataFeed:
    def __init__(self):
        # Proxy Configuration for Streamlit Cloud (US Region Block Fix)
        # Streamlit Cloud servers are in the US, where Binance/Bybit are blocked.
        proxies = {}
        try:
            if "PROXY" in st.secrets:
                proxies = {
                    'http': st.secrets["PROXY"],
                    'https': st.secrets["PROXY"]
                }
        except Exception:
            pass # Ignore if secrets are not configured locally

        self.coinalyze_api_key = None
        try:
            if "COINALYZE_API_KEY" in st.secrets:
                self.coinalyze_api_key = st.secrets["COINALYZE_API_KEY"]
        except Exception:
            pass

        # Initialize the Binance USD-M Futures exchange
        self.exchange = ccxt.binanceusdm({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
            'proxies': proxies
        })
        
        # CRITICAL FIX: Load market metadata immediately upon initialization
        # This prevents the "markets not loaded" error when looking up symbols later.
        try:
            self.exchange.load_markets()
        except Exception as e:
            if "451" in str(e) or "Service unavailable" in str(e):
                st.error("⚠️ **ACCESS DENIED (GEO-BLOCK):** Streamlit Cloud servers are in the US, where Binance is restricted. Please configure a Proxy in 'Secrets'.")
            else:
                st.error(f"System Init Failure: Could not load Binance markets. {e}")

        # Initialize ByBit for additional data (Explicitly using V5 via 'linear' option)
        self.bybit = ccxt.bybit({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear',  # This ensures V5 API for USDT Perpetuals
            },
            'proxies': proxies
        })
        try:
            self.bybit.load_markets()
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                st.warning("⚠️ ByBit access restricted (US Server).")
            else:
                st.error(f"System Init Failure: Could not load ByBit markets. {e}")

    @st.cache_data(ttl=3)
    def fetch_market_data(_self, symbol, timeframe='15m', limit=100):
        """
        Fetches OHLCV + Taker Buy Volume (Raw Kernel Access)
        Handles Binance (Primary) and Bybit (Secondary/Fallback)
        TTL=3s for scalping precision
        """
        try:
            # Ensure markets are loaded
            if not _self.exchange.markets:
                _self.exchange.load_markets()
            if not _self.bybit.markets:
                _self.bybit.load_markets()

            # Check Availability
            in_binance = symbol in _self.exchange.markets
            
            # Bybit Symbol Resolution
            bybit_symbol = symbol
            if not symbol.endswith(':USDT'):
                bybit_symbol = symbol + ":USDT"
            
            in_bybit = bybit_symbol in _self.bybit.markets

            df = pd.DataFrame()
            funding_binance = {}
            funding_bybit = {}
            is_cvd_estimated = False

            # --- 1. FETCH OHLCV & VOLUME ---
            fetch_success = False

            if in_binance:
                try:
                    # Use Binance (Preferred for Taker Buy Vol)
                    market = _self.exchange.market(symbol)
                    response = _self.exchange.public_get_klines({
                        'symbol': market['id'],
                        'interval': timeframe,
                        'limit': limit
                    })
                    
                    data = []
                    for row in response:
                        data.append({
                            'timestamp': int(row[0]),
                            'open': float(row[1]),
                            'high': float(row[2]),
                            'low': float(row[3]),
                            'close': float(row[4]),
                            'volume': float(row[5]),
                            'taker_buy_vol': float(row[9]) 
                        })
                    df = pd.DataFrame(data)
                    fetch_success = True
                    is_cvd_estimated = False
                except Exception as e:
                    print(f"Binance fetch failed for {symbol}: {e}")
                    # Fallthrough to Bybit check
                
            if not fetch_success and in_bybit:
                # Try Coinalyze for real Taker Volume (CVD) if API key available
                if _self.coinalyze_api_key:
                    try:
                        interval_map = {'1m': '1minute', '5m': '5minute', '15m': '15minute', '30m': '30minute', '1h': '1hour', '2h': '2hour', '4h': '4hour', '6h': '6hour', '12h': '12hour', '1d': 'daily'}
                        interval_str = interval_map.get(timeframe, '15minute')
                        base = symbol.split('/')[0]
                        quote = symbol.split('/')[1].split(':')[0]
                        coinalyze_symbol = f"{base}{quote}_PERP.3"
                        
                        url = f"https://api.coinalyze.net/v1/ohlcv-history"
                        params = {'symbols': coinalyze_symbol, 'interval': interval_str}
                        headers = {'api_key': _self.coinalyze_api_key}
                        
                        res = requests.get(url, params=params, headers=headers, timeout=5)
                        if res.status_code == 200:
                            data_json = res.json()
                            if data_json and len(data_json) > 0 and 'history' in data_json[0]:
                                ohlcv_hist = data_json[0]['history']
                                data = []
                                for row in ohlcv_hist:
                                    data.append({
                                        'timestamp': int(row['t']) * 1000,
                                        'open': float(row['o']),
                                        'high': float(row['h']),
                                        'low': float(row['l']),
                                        'close': float(row['c']),
                                        'volume': float(row['v']),
                                        'taker_buy_vol': float(row.get('bv', float(row['v']) * 0.5))
                                    })
                                df = pd.DataFrame(data)
                                fetch_success = True
                                is_cvd_estimated = False
                    except Exception as e:
                        print(f"Coinalyze OHLCV fetch failed: {e}")

                if not fetch_success:
                    # Fallback to Bybit CCXT
                    ohlcv = _self.bybit.fetch_ohlcv(bybit_symbol, timeframe, limit=limit)
                    data = []
                    for row in ohlcv:
                        vol = float(row[5])
                        data.append({
                            'timestamp': int(row[0]),
                            'open': float(row[1]),
                            'high': float(row[2]),
                            'low': float(row[3]),
                            'close': float(row[4]),
                            'volume': vol,
                            'taker_buy_vol': None # Real Taker Vol info not in OHLCV, passing None to avoid corrupting CVD
                        })
                    df = pd.DataFrame(data)
                    fetch_success = True
                    is_cvd_estimated = True
            
            if not fetch_success:
                st.error(f"Symbol {symbol} not found on Binance or Bybit.")
                return pd.DataFrame(), {}

            if df.empty:
                return pd.DataFrame(), {}

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['is_cvd_estimated'] = is_cvd_estimated

            # --- 2. FETCH OPEN INTEREST ---
            
            # Helper to fetch from Coinalyze
            def fetch_coinalyze_oi(symbol_suffix):
                if not _self.coinalyze_api_key: return None
                try:
                    # Mapping timeframe to Coinalyze interval
                    interval_map = {
                        '1m': '1minute', '5m': '5minute', '15m': '15minute',
                        '30m': '30minute', '1h': '1hour', '2h': '2hour',
                        '4h': '4hour', '6h': '6hour', '12h': '12hour', '1d': 'daily'
                    }
                    interval_str = interval_map.get(timeframe, '15minute')
                    
                    # Convert 'BTC/USDT:USDT' to Coinalyze format (e.g. 'BTCUSDT_PERP')
                    base = symbol.split('/')[0]
                    quote = symbol.split('/')[1].split(':')[0]
                    coinalyze_symbol = f"{base}{quote}_PERP.{symbol_suffix}"
                    
                    url = f"https://api.coinalyze.net/v1/open-interest-history"
                    params = {'symbols': coinalyze_symbol, 'interval': interval_str}
                    headers = {'api_key': _self.coinalyze_api_key}
                    
                    res = requests.get(url, params=params, headers=headers, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if data and len(data) > 0 and 'history' in data[0]:
                            oi_history = data[0]['history']
                            oi_df = pd.DataFrame(oi_history)
                            # Coinalyze timestamp is in seconds
                            oi_df['timestamp'] = pd.to_datetime(oi_df['t'], unit='s')
                            oi_df.rename(columns={'v': 'oi_value'}, inplace=True)
                            return oi_df[['timestamp', 'oi_value']]
                except Exception as e:
                    print(f"Coinalyze OI fetch failed: {e}")
                return None

            # Binance OI
            coinalyze_binance_oi = fetch_coinalyze_oi('A') if in_binance else None
            
            if coinalyze_binance_oi is not None and not coinalyze_binance_oi.empty:
                coinalyze_binance_oi.rename(columns={'oi_value': 'oi'}, inplace=True)
                df = pd.merge(df, coinalyze_binance_oi, on='timestamp', how='left')
                df['oi'] = df['oi'].ffill()
            elif in_binance:
                try:
                    oi_data = _self.exchange.fetch_open_interest_history(symbol, timeframe, limit=limit)
                    oi_df = pd.DataFrame(oi_data)
                    oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')
                    oi_df = oi_df[['timestamp', 'openInterestValue']]
                    oi_df.rename(columns={'openInterestValue': 'oi'}, inplace=True)
                    df = pd.merge(df, oi_df, on='timestamp', how='left')
                    df['oi'] = df['oi'].ffill()
                except:
                    df['oi'] = 0
            else:
                df['oi'] = 0

            # Bybit OI (Coinalyze Bybit is .3 generally, but fallback to CCXT is fine)
            coinalyze_bybit_oi = fetch_coinalyze_oi('3') if in_bybit else None
            
            if coinalyze_bybit_oi is not None and not coinalyze_bybit_oi.empty:
                coinalyze_bybit_oi.rename(columns={'oi_value': 'oi_bybit'}, inplace=True)
                df = pd.merge(df, coinalyze_bybit_oi, on='timestamp', how='left')
                df['oi_bybit'] = df['oi_bybit'].ffill()
            elif in_bybit:
                try:
                    oi_bybit_data = _self.bybit.fetch_open_interest_history(bybit_symbol, timeframe, limit=limit)
                    oi_bybit_df = pd.DataFrame(oi_bybit_data)
                    oi_bybit_df['timestamp'] = pd.to_datetime(oi_bybit_df['timestamp'], unit='ms')
                    oi_bybit_df = oi_bybit_df[['timestamp', 'openInterestAmount']]
                    oi_bybit_df.rename(columns={'openInterestAmount': 'oi_bybit'}, inplace=True)
                    
                    df = pd.merge(df, oi_bybit_df, on='timestamp', how='left')
                    df['oi_bybit'] = df['oi_bybit'].ffill()
                except:
                    df['oi_bybit'] = 0
            else:
                df['oi_bybit'] = 0

            # --- 3. FETCH FUNDING RATES ---
            def detect_funding_interval(funding_data, exchange_name):
                """Detect funding interval from API response"""
                if not funding_data:
                    return 'N/A'
                
                try:
                    # Method 1: Check CCXT normalized 'interval' field (top-level)
                    if 'interval' in funding_data and funding_data['interval']:
                        interval_ms = funding_data['interval']
                        if isinstance(interval_ms, (int, float)):
                            hours = interval_ms / (1000 * 60 * 60)
                            if hours <= 1.5:
                                return '1h'
                            elif hours <= 4.5:
                                return '4h'
                            elif hours <= 8.5:
                                return '8h'
                            else:
                                return f'{int(hours)}h'
                    
                    # Method 2: Check exchange-specific fields in info
                    if 'info' in funding_data:
                        info = funding_data['info']
                        
                        # ByBit: fundingIntervalHour
                        if 'fundingIntervalHour' in info:
                            hours = int(info['fundingIntervalHour'])
                            return f'{hours}h'
                        
                        # Binance: fundingIntervalHours (if present)
                        if 'fundingIntervalHours' in info:
                            hours = int(info['fundingIntervalHours'])
                            return f'{hours}h'
                    
                    # Method 3: Calculate from next funding timestamp (fallback)
                    if 'fundingTimestamp' in funding_data and funding_data['fundingTimestamp']:
                        import datetime
                        next_funding = funding_data['fundingTimestamp']
                        current_time = datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000
                        diff_ms = next_funding - current_time
                        
                        if diff_ms > 0:
                            diff_hours = diff_ms / (1000 * 60 * 60)
                            # Round to nearest standard interval
                            if diff_hours <= 1.5:
                                return '1h'
                            elif diff_hours <= 4.5:
                                return '4h'
                            elif diff_hours <= 8.5:
                                return '8h'
                            else:
                                return f'{int(round(diff_hours))}h'
                except Exception as e:
                    print(f"Error detecting funding interval for {exchange_name}: {e}")
                
                # Default
                return '8h'
            
            if in_binance:
                try:
                    funding_binance = _self.exchange.fetch_funding_rate(symbol)
                    funding_binance['fundingInterval'] = detect_funding_interval(funding_binance, 'binance')
                except Exception as e:
                    print(f"Binance funding fetch error: {e}")
            
            if in_bybit:
                try:
                    funding_bybit = _self.bybit.fetch_funding_rate(bybit_symbol)
                    funding_bybit['fundingInterval'] = detect_funding_interval(funding_bybit, 'bybit')
                except Exception as e:
                    print(f"Bybit funding fetch error: {e}")

            return df, {"binance": funding_binance, "bybit": funding_bybit}

        except Exception as e:
            st.error(f"Data Feed Error: {e}")
            return pd.DataFrame(), {}

    def get_macro_context(self, timeframe='15m'):
        """Fetches Global Market Data (BTC.D, USDT.D) and BTC Price with Change."""
        try:
            # 1. Fetch BTC Price & Change from Exchange
            if not self.exchange.markets:
                self.exchange.load_markets()
            
            btc_price = 0
            btc_change = 0
            
            try:
                # Fetch OHLCV for timeframe change
                ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', timeframe, limit=2)
                if len(ohlcv) >= 2:
                    open_price = ohlcv[-1][1] # Open of current candle
                    close_price = ohlcv[-1][4] # Current close (live)
                    btc_price = close_price
                    btc_change = ((close_price - open_price) / open_price) * 100
                else:
                    ticker = self.exchange.fetch_ticker('BTC/USDT')
                    btc_price = ticker['last']
                    btc_change = ticker['percentage']
            except:
                pass

            # 2. Fetch Global Data from CoinGecko (REMOVED)
            btc_d = 0
            eth_d = 0
            usdt_d = 0
            btc_d_change = 0
            eth_d_change = 0
            usdt_d_change = 0
            
            # Try to fetch from CoinGecko Public API (No Auth)
            try:
                url = "https://api.coingecko.com/api/v3/global"
                data = requests.get(url, timeout=2).json()
                market_cap_pct = data['data']['market_cap_percentage']
                
                btc_d = market_cap_pct.get('btc', 0)
                eth_d = market_cap_pct.get('eth', 0)
                usdt_d = market_cap_pct.get('usdt', 0)
                
                # Change data is not directly available in this endpoint, setting to 0 or calculating if history available
                # For now, we will just show the current value.
            except:
                pass
                
            return {
                'price': btc_price,
                'change': btc_change,
                'btc_d': btc_d,
                'eth_d': eth_d,
                'usdt_d': usdt_d,
                'btc_d_change': btc_d_change,
                'eth_d_change': eth_d_change,
                'usdt_d_change': usdt_d_change
            }
        except:
            return {
                'price': 0, 'change': 0, 
                'btc_d': 0, 'eth_d': 0, 'usdt_d': 0, 
                'btc_d_change': 0, 'eth_d_change': 0, 'usdt_d_change': 0
            }

    def get_symbols(self):
        """Returns a list of active USDT perpetual symbols sorted by 24h Volume (Desc)."""
        # Use the cached function to prevent API spam and timeouts
        proxies = self.exchange.proxies if hasattr(self.exchange, 'proxies') else None
        symbols = fetch_symbols_sorted_by_volume(proxies)
        
        if symbols:
            return symbols
            
        # Fallback to basic list if tickers fail
        try:
            if not self.exchange.markets:
                self.exchange.load_markets()
            symbols = []
            for market in self.exchange.markets.values():
                if market.get('quote') == 'USDT' and market.get('swap') and market.get('active', True):
                    symbols.append(market['symbol'])
            return sorted(symbols)
        except:
            return []

    def _make_request(self, url, params=None):
        """Helper to make requests with retries."""
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)
        
        try:
            resp = session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise e

    @st.cache_data(ttl=3600) # Cache for 1 hour
    def fetch_fundamental_data(_self, symbol):
        """Fetches fundamental data from CoinGecko."""
        # DEPRECATED: CoinGecko removed.
        return None
