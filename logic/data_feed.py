import ccxt
import pandas as pd
import streamlit as st
import requests

@st.cache_data(ttl=86400)
def get_all_coins_list_v2():
    """Fetches the full list of coins from CoinGecko (Cached for 24h)."""
    # No try-except here to prevent caching failures (empty lists)
    # If this fails, it raises an exception, and Streamlit won't cache the result.
    resp = requests.get("https://api.coingecko.com/api/v3/coins/list", timeout=30)
    resp.raise_for_status()
    return resp.json()

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

    @st.cache_data(ttl=10)
    def fetch_market_data(_self, symbol, timeframe='15m', limit=100):
        """
        Fetches OHLCV + Taker Buy Volume (Raw Kernel Access)
        Handles Binance (Primary) and Bybit (Secondary/Fallback)
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
                except Exception as e:
                    print(f"Binance fetch failed for {symbol}: {e}")
                    # Fallthrough to Bybit check
                
            if not fetch_success and in_bybit:
                # Fallback to Bybit
                ohlcv = _self.bybit.fetch_ohlcv(bybit_symbol, timeframe, limit=limit)
                data = []
                for row in ohlcv:
                    # Bybit doesn't provide Taker Buy Vol in standard OHLCV
                    # We estimate it as 50% of volume to prevent CVD crash (Neutral)
                    vol = float(row[5])
                    data.append({
                        'timestamp': int(row[0]),
                        'open': float(row[1]),
                        'high': float(row[2]),
                        'low': float(row[3]),
                        'close': float(row[4]),
                        'volume': vol,
                        'taker_buy_vol': vol * 0.5 
                    })
                df = pd.DataFrame(data)
                fetch_success = True
            
            if not fetch_success:
                st.error(f"Symbol {symbol} not found on Binance or Bybit.")
                return pd.DataFrame(), {}

            if df.empty:
                return pd.DataFrame(), {}

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # --- 2. FETCH OPEN INTEREST ---
            
            # Binance OI
            if in_binance:
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
                df['oi'] = 0 # No Binance OI

            # Bybit OI
            if in_bybit:
                try:
                    oi_bybit_data = _self.bybit.fetch_open_interest_history(bybit_symbol, timeframe, limit=limit)
                    oi_bybit_df = pd.DataFrame(oi_bybit_data)
                    oi_bybit_df['timestamp'] = pd.to_datetime(oi_bybit_df['timestamp'], unit='ms')
                    oi_bybit_df = oi_bybit_df[['timestamp', 'openInterestAmount']]
                    oi_bybit_df.rename(columns={'openInterestAmount': 'oi_bybit_amount'}, inplace=True)
                    
                    df = pd.merge(df, oi_bybit_df, on='timestamp', how='left')
                    df['oi_bybit_amount'] = df['oi_bybit_amount'].ffill()
                    df['oi_bybit'] = df['oi_bybit_amount'] * df['close']
                except:
                    df['oi_bybit'] = 0
            else:
                df['oi_bybit'] = 0

            # --- 3. FETCH FUNDING RATES ---
            if in_binance:
                try:
                    funding_binance = _self.exchange.fetch_funding_rate(symbol)
                except:
                    pass
            
            if in_bybit:
                try:
                    funding_bybit = _self.bybit.fetch_funding_rate(bybit_symbol)
                except:
                    pass

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

            # 2. Fetch Global Data from CoinGecko
            btc_d = 0
            usdt_d = 0
            btc_d_change = 0
            usdt_d_change = 0
            
            try:
                # A. Global Data
                resp = requests.get("https://api.coingecko.com/api/v3/global")
                data = resp.json().get('data', {})
                market_cap_pct = data.get('market_cap_percentage', {})
                btc_d = market_cap_pct.get('btc', 0)
                usdt_d = market_cap_pct.get('usdt', 0)
                total_cap_change = data.get('market_cap_change_percentage_24h_usd', 0)
                
                # B. Individual Coin Data for Dominance Change Calculation
                # We need market_cap_change_percentage_24h for BTC and USDT
                coins_resp = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={
                    'vs_currency': 'usd',
                    'ids': 'bitcoin,tether'
                })
                coins_data = coins_resp.json()
                
                btc_cap_change = 0
                usdt_cap_change = 0
                
                for coin in coins_data:
                    if coin['id'] == 'bitcoin':
                        btc_cap_change = coin.get('market_cap_change_percentage_24h', 0)
                    elif coin['id'] == 'tether':
                        usdt_cap_change = coin.get('market_cap_change_percentage_24h', 0)
                
                # C. Calculate Dominance Change
                # Formula: ((1 + coin_change/100) / (1 + total_change/100) - 1) * 100
                if total_cap_change is not None:
                    if btc_cap_change is not None:
                        btc_d_change = ((1 + btc_cap_change/100) / (1 + total_cap_change/100) - 1) * 100
                    if usdt_cap_change is not None:
                        usdt_d_change = ((1 + usdt_cap_change/100) / (1 + total_cap_change/100) - 1) * 100
                        
            except Exception as e:
                print(f"Macro Data Error: {e}")
                
            return {
                'price': btc_price,
                'change': btc_change,
                'btc_d': btc_d,
                'usdt_d': usdt_d,
                'btc_d_change': btc_d_change,
                'usdt_d_change': usdt_d_change
            }
        except:
            return {'price': 0, 'change': 0, 'btc_d': 0, 'usdt_d': 0, 'btc_d_change': 0, 'usdt_d_change': 0}

    def get_symbols(self):
        """Returns a list of active USDT perpetual symbols for selection."""
        try:
            if not self.exchange.markets:
                self.exchange.load_markets()
            symbols = []
            for market in self.exchange.markets.values():
                if not market.get('active', True):
                    continue
                if market.get('quote') != 'USDT':
                    continue
                if not market.get('swap'):
                    continue
                symbols.append(market['symbol'])
            return sorted(set(symbols))
        except Exception as e:
            st.error(f"Symbol Load Error: {e}")
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
        # Note: We raise exceptions here so Streamlit DOES NOT cache the failure (None).
        # The caller (main.py) should handle the exception.
        
        base_symbol = symbol.split('/')[0].lower()
        
        # 1. Search for Coin ID
        search_url = "https://api.coingecko.com/api/v3/search"
        # We use a direct request here or use the helper? Helper is better.
        # But _make_request is an instance method, and this is a cached method which might be static-like?
        # _self is the instance.
        
        try:
            data = _self._make_request(search_url, params={'query': base_symbol})
        except Exception:
            # If search fails, we might still try the fallback list?
            data = {}
        
        coin_id = None
        for coin in data.get('coins', []):
            if coin['symbol'].lower() == base_symbol:
                coin_id = coin['id']
                break
        
        # If search didn't find an exact match, try the full list
        if not coin_id:
            try:
                all_coins = get_all_coins_list_v2()
            except Exception:
                all_coins = []

            matches = [c for c in all_coins if c['symbol'].lower() == base_symbol]
            
            if matches:
                # Heuristic: Prefer exact name match if possible
                exact_name_match = next((c for c in matches if c['name'].lower() == base_symbol), None)
                if exact_name_match:
                    coin_id = exact_name_match['id']
                else:
                    coin_id = matches[0]['id']

        if not coin_id:
            raise Exception(f"Coin ID not found for {base_symbol}")

        # 2. Fetch Details
        details_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'false',
            'developer_data': 'false',
            'sparkline': 'false'
        }
        
        details = _self._make_request(details_url, params=params)
        
        if 'market_data' not in details:
            raise Exception("No market data in response")
        
        return details
