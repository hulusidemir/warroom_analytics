import numpy as np
import pandas as pd

class QuantLogic:
    
    @staticmethod
    def calculate_vwap(df):
        """Daily Anchored VWAP (Resets every day)"""
        if df.empty: return df
        df['date'] = df['timestamp'].dt.date
        
        def calc_vwap_group(group):
            v = group['volume']
            tp = (group['high'] + group['low'] + group['close']) / 3
            # Ensure it returns a Series with the original index
            result = (tp * v).cumsum() / v.cumsum()
            return result
            
        # Fixed: Added include_groups=False to suppress FutureWarning
        vwap_series = df.groupby('date', group_keys=False).apply(calc_vwap_group, include_groups=False)
        # Check if pandas returned a DataFrame inappropriately and extract the single column/series
        if isinstance(vwap_series, pd.DataFrame):
             # Try to get the first column
             vwap_series = vwap_series.iloc[:, 0]
        
        df['vwap'] = vwap_series.values if hasattr(vwap_series, 'values') else vwap_series
        return df

    @staticmethod
    def calculate_cvd(df):
        """
        Calculates Cumulative Volume Delta (CVD) without daily reset.
        For scalping, intraday momentum must persist across session boundaries.
        """
        if df.empty: return df
        
        if df['taker_buy_vol'].isnull().all():
            df['cvd'] = 0
            df['delta'] = 0
            return df

        df['taker_buy_vol'] = df['taker_buy_vol'].fillna(df['volume'] * 0.5)
        df['taker_sell_vol'] = df['volume'] - df['taker_buy_vol']
        df['delta'] = df['taker_buy_vol'] - df['taker_sell_vol']
        
        # Continuous CVD (No Reset) - Critical for scalping momentum
        df['cvd'] = df['delta'].cumsum()
        return df

    @staticmethod
    def calculate_atr(df, period=14):
        """Average True Range for Volatility"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(window=period).mean()
        return df

    @staticmethod
    def identify_oi_regime(df):
        """
        Classifies the market state based on Price, OI Delta, and CVD (Delta).
        Uses ATR-based Dynamic Thresholds to filter noise.
        """
        # Ensure ATR is calculated
        if 'atr' not in df.columns:
            df = QuantLogic.calculate_atr(df)
            
        # Calculate changes/deltas - FIXED: Use close-to-close momentum
        df['price_change'] = df['close'].diff()
        df['oi_change_pct'] = df['oi'].pct_change() * 100
        
        # Fill NaN values
        df['price_change'] = df['price_change'].fillna(0)
        df['oi_change_pct'] = df['oi_change_pct'].fillna(0)
        
        # Check if OI data is valid
        oi_is_valid = df['oi'].sum() > 0 and not df['oi'].isnull().all()
        
        # Adaptive ATR threshold based on recent volatility
        # Higher volatility = higher threshold to avoid false signals
        volatility_ratio = df['atr'].rolling(10).std() / df['atr'].rolling(10).mean()
        volatility_ratio = volatility_ratio.fillna(1.0)
        adaptive_atr_multiplier = 0.15 + (volatility_ratio * 0.1)
        adaptive_atr_multiplier = adaptive_atr_multiplier.clip(0.1, 0.3)
        
        df['bull_trend'] = df['price_change'] > (adaptive_atr_multiplier * df['atr'])
        df['bear_trend'] = df['price_change'] < -(adaptive_atr_multiplier * df['atr'])
        
        # Dynamic OI Threshold based on recent OI volatility
        if oi_is_valid:
            oi_std = df['oi_change_pct'].rolling(20).std()
            oi_thresh = (oi_std * 1.5).fillna(0.05).clip(0.02, 0.15)
        else:
            oi_thresh = 0.0
        
        if 'delta' not in df.columns:
            df['delta'] = 0
        
        # Delta magnitude threshold - FIXED: Consider delta strength
        delta_std = df['delta'].rolling(20).std().fillna(1)
        delta_threshold = delta_std * 0.3
        df['strong_positive_delta'] = df['delta'] > delta_threshold
        df['strong_negative_delta'] = df['delta'] < -delta_threshold

        # If OI data is invalid, use simple price-based regime
        if not oi_is_valid:
            simple_conditions = [
                (df['bull_trend']) & (df['strong_positive_delta']),
                (df['bull_trend']) & (~df['strong_positive_delta']),
                (df['bear_trend']) & (df['strong_negative_delta']),
                (df['bear_trend']) & (~df['strong_negative_delta']),
                (df['price_change'] > 0) & (~df['bull_trend']),
                (df['price_change'] < 0) & (~df['bear_trend'])
            ]
            simple_choices = [
                'Strong Long Buildup 🟢🔥',
                'Absorption Long Buildup 🟢🛡️',
                'Strong Short Buildup 🔴🔥',
                'Absorption Short Buildup 🔴🛡️',
                'Minor Long Bias 🟢',
                'Minor Short Bias 🔴'
            ]
            df['regime'] = np.select(simple_conditions, simple_choices, default='Neutral')
            return df
        
        # Use dynamic thresholds and magnitude-aware delta
        conditions = [
            (df['bull_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['strong_positive_delta']), # Strong Long Buildup
            (df['bull_trend']) & (df['oi_change_pct'] > oi_thresh) & (~df['strong_positive_delta']), # Absorption Long Buildup
            
            (df['bull_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['strong_positive_delta']), # Short Covering (Aggressive)
            (df['bull_trend']) & (df['oi_change_pct'] < -oi_thresh) & (~df['strong_positive_delta']), # Short Covering (Passive)
            
            (df['bear_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['strong_negative_delta']), # Strong Short Buildup
            (df['bear_trend']) & (df['oi_change_pct'] > oi_thresh) & (~df['strong_negative_delta']), # Absorption Short Buildup
            
            (df['bear_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['strong_negative_delta']), # Long Liquidation (Aggressive)
            (df['bear_trend']) & (df['oi_change_pct'] < -oi_thresh) & (~df['strong_negative_delta'])  # Long Liquidation (Passive)
        ]
        
        choices = [
            'Strong Long Buildup 🟢🔥',
            'Absorption Long Buildup 🟢🛡️',
            'Short Covering 👻🔥',
            'Passive Short Covering 👻🛡️',
            'Strong Short Buildup 🔴🔥',
            'Absorption Short Buildup 🔴🛡️',
            'Long Liquidation 🩸🔥',
            'Passive Long Liquidation 🩸🛡️'
        ]
        
        # Improved generic conditions for minor movements
        generic_conditions = [
            (df['price_change'] > 0) & (~df['bull_trend']) & (df['oi_change_pct'] > oi_thresh),
            (df['price_change'] > 0) & (~df['bull_trend']) & (df['oi_change_pct'] <= oi_thresh),
            (df['price_change'] < 0) & (~df['bear_trend']) & (df['oi_change_pct'] > oi_thresh),
            (df['price_change'] < 0) & (~df['bear_trend']) & (df['oi_change_pct'] <= oi_thresh),
        ]
        generic_choices = [
            'Minor Long Bias 🟢',
            'Minor Long Bias 🟢',
            'Minor Short Bias 🔴',
            'Minor Short Bias 🔴'
        ]
        
        df['regime'] = np.select(conditions, choices, default=np.select(generic_conditions, generic_choices, default='Neutral'))
        return df

    @staticmethod
    def detect_sfp(df):
        """
        Session-Based Liquidity Hunt Detector (SFP).
        For scalping, uses recent session highs/lows (last 8-12 hours) instead of daily.
        """
        df['sfp_signal'] = None
        
        # Calculate rolling session highs/lows (8-hour window for 15m = 32 candles)
        # This captures Asian/London/NY session patterns
        window = min(32, len(df) // 3)  # Adaptive to data length
        
        df['session_high'] = df['high'].rolling(window=window, min_periods=1).max().shift(1)
        df['session_low'] = df['low'].rolling(window=window, min_periods=1).min().shift(1)
        
        # Bullish SFP: Price wicks below session low but closes above it
        bull_sfp = (df['low'] < df['session_low']) & (df['close'] > df['session_low'])
        
        # Bearish SFP: Price wicks above session high but closes below it
        bear_sfp = (df['high'] > df['session_high']) & (df['close'] < df['session_high'])
        
        df.loc[bull_sfp, 'sfp_signal'] = 'Bullish SFP 🚀'
        df.loc[bear_sfp, 'sfp_signal'] = 'Bearish SFP 🔻'
        
        return df

    @staticmethod
    def calculate_rsi(df, period=14):
        """Relative Strength Index"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    @staticmethod
    def calculate_mfi(df, period=14):
        """Money Flow Index (Volume-weighted RSI) - FIXED: Use close price diff"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        # FIXED: Compare close price, not typical price
        price_diff = df['close'].diff()
        
        pos_flow = pd.Series(0.0, index=df.index)
        neg_flow = pd.Series(0.0, index=df.index)
        
        pos_flow[price_diff > 0] = money_flow[price_diff > 0]
        neg_flow[price_diff < 0] = money_flow[price_diff < 0]
        
        # Rolling sums
        pos_mf = pos_flow.rolling(window=period).sum()
        neg_mf = neg_flow.rolling(window=period).sum()
        
        # Prevent division by zero
        mfi_ratio = pos_mf / neg_mf.replace(0, 0.0001)
        df['mfi'] = 100 - (100 / (1 + mfi_ratio))
        return df

    @staticmethod
    def calculate_obv(df):
        """On-Balance Volume"""
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return df

    @staticmethod
    def calculate_cmf(df, period=20):
        """Chaikin Money Flow - FIXED: Division by zero protection"""
        # Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
        range_val = df['high'] - df['low']
        range_val = range_val.replace(0, 0.0001)  # Prevent division by zero
        
        mf_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / range_val
        mf_volume = mf_multiplier * df['volume']
        
        volume_sum = df['volume'].rolling(window=period).sum().replace(0, 1)  # Prevent division by zero
        df['cmf'] = mf_volume.rolling(window=period).sum() / volume_sum
        return df

    @staticmethod
    def calculate_bollinger_bands(df, period=20, std_dev=2):
        """Bollinger Bands"""
        df['bb_mid'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * std_dev)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * std_dev)
        return df

    @staticmethod
    def calculate_macd(df, fast=12, slow=26, signal=9):
        """Moving Average Convergence Divergence"""
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    @staticmethod
    def calculate_stoch_rsi(df, period=14, smooth_k=3, smooth_d=3):
        """Stochastic RSI"""
        # Calculate RSI first if not present, but usually it is. 
        # Assuming RSI is already calculated or calculating it here temporarily
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        min_rsi = rsi.rolling(window=period).min()
        max_rsi = rsi.rolling(window=period).max()
        
        stoch = ((rsi - min_rsi) / (max_rsi - min_rsi)) * 100
        df['stoch_k'] = stoch.rolling(window=smooth_k).mean()
        df['stoch_d'] = df['stoch_k'].rolling(window=smooth_d).mean()
        return df

    @staticmethod
    def calculate_ichimoku(df):
        """Ichimoku Cloud"""
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        df['tenkan_sen'] = (high_9 + low_9) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        df['kijun_sen'] = (high_26 + low_26) / 2

        # Senkou Span A (Leading Span A): (Conversion Line + Base Line) / 2
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
        high_52 = df['high'].rolling(window=52).max()
        low_52 = df['low'].rolling(window=52).min()
        df['senkou_span_b'] = ((high_52 + low_52) / 2).shift(26)

        # Chikou Span (Lagging Span): Close shifted back 26 periods
        df['chikou_span'] = df['close'].shift(-26)
        
        return df

    @staticmethod
    def calculate_parabolic_sar(df, af=0.02, max_af=0.2):
        """Parabolic SAR"""
        # Initialize columns
        df['psar'] = df['close'][0]
        df['psar_bull'] = True
        df['af'] = af
        df['ep'] = df['high'][0] # Extreme Point
        
        psar = df['close'][0]
        bull = True
        af_val = af
        ep = df['high'][0]
        
        psar_values = [psar]
        
        # Iterative calculation (SAR is recursive)
        for i in range(1, len(df)):
            prev_psar = psar
            prev_bull = bull
            
            # Calculate current SAR
            psar = prev_psar + af_val * (ep - prev_psar)
            
            # Trend Switch Logic
            if prev_bull:
                if df['low'][i] < psar:
                    bull = False
                    psar = ep
                    ep = df['low'][i]
                    af_val = af
                else:
                    if df['high'][i] > ep:
                        ep = df['high'][i]
                        af_val = min(af_val + af, max_af)
                    # SAR cannot be higher than previous two lows in uptrend
                    if i > 1:
                        psar = min(psar, df['low'][i-1], df['low'][i-2])
                        
            else: # Bearish
                if df['high'][i] > psar:
                    bull = True
                    psar = ep
                    ep = df['high'][i]
                    af_val = af
                else:
                    if df['low'][i] < ep:
                        ep = df['low'][i]
                        af_val = min(af_val + af, max_af)
                    # SAR cannot be lower than previous two highs in downtrend
                    if i > 1:
                        psar = max(psar, df['high'][i-1], df['high'][i-2])
            
            psar_values.append(psar)
            
        df['psar'] = psar_values
        return df

    @staticmethod
    def add_funding_pressure(df, funding_rate_binance=0, funding_rate_bybit=0):
        """
        Adds funding rate pressure analysis to regime detection.
        Critical for scalping: Extreme funding = squeeze potential.
        """
        # Average funding rate from both exchanges
        avg_funding = (funding_rate_binance + funding_rate_bybit) / 2
        
        # Funding pressure zones
        df['funding_pressure'] = 'Neutral'
        
        if avg_funding > 0.01:  # 1% = Very high long funding
            df['funding_pressure'] = 'Long Squeeze Risk 🔴'
        elif avg_funding > 0.005:  # 0.5% = High long funding
            df['funding_pressure'] = 'High Long Funding ⚠️'
        elif avg_funding < -0.01:  # -1% = Very high short funding
            df['funding_pressure'] = 'Short Squeeze Risk 🟢'
        elif avg_funding < -0.005:  # -0.5% = High short funding
            df['funding_pressure'] = 'High Short Funding 💎'
        
        return df
    
    @staticmethod
    def calculate_ema_trend(df, fast_period=21, slow_period=50):
        """Calculate EMA-based trend for proper trend detection"""
        df['ema_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
        df['ema_trend'] = df['ema_fast'] > df['ema_slow']
        return df

    @staticmethod
    def detect_divergences(df, window=5):
        """
        Detects Regular Bullish/Bearish Divergences for RSI, MFI, CMF, MACD.
        """
        # Helper to find local peaks/troughs
        def is_peak(series, idx, w):
            if idx < w or idx >= len(series) - w: return False
            return series[idx] == series[idx-w:idx+w+1].max()

        def is_trough(series, idx, w):
            if idx < w or idx >= len(series) - w: return False
            return series[idx] == series[idx-w:idx+w+1].min()

        # We only check the last few candles for a divergence signal
        last_idx = len(df) - 2 # Check slightly back to ensure peak is formed
        
        signals = []
        
        # Indicators to check
        indicators = ['rsi', 'mfi', 'cmf', 'macd']
        
        for ind in indicators:
            if ind not in df.columns: continue
            
            # Check Bearish Divergence (Price HH, Indicator LH)
            # Find last peak in Price
            price_peak_idx = -1
            for i in range(last_idx, last_idx - 20, -1):
                if is_peak(df['high'], i, window):
                    price_peak_idx = i
                    break
            
            if price_peak_idx != -1:
                # Find previous peak
                prev_price_peak_idx = -1
                for i in range(price_peak_idx - 1, price_peak_idx - 50, -1):
                    if is_peak(df['high'], i, window):
                        prev_price_peak_idx = i
                        break
                
                if prev_price_peak_idx != -1:
                    # Check Price HH
                    if df['high'].iloc[price_peak_idx] > df['high'].iloc[prev_price_peak_idx]:
                        # Check Indicator LH
                        if df[ind].iloc[price_peak_idx] < df[ind].iloc[prev_price_peak_idx]:
                            signals.append(f"Bearish {ind.upper()} Divergence")

            # Check Bullish Divergence (Price LL, Indicator HL)
            # Find last trough in Price
            price_trough_idx = -1
            for i in range(last_idx, last_idx - 20, -1):
                if is_trough(df['low'], i, window):
                    price_trough_idx = i
                    break
            
            if price_trough_idx != -1:
                # Find previous trough
                prev_price_trough_idx = -1
                for i in range(price_trough_idx - 1, price_trough_idx - 50, -1):
                    if is_trough(df['low'], i, window):
                        prev_price_trough_idx = i
                        break
                
                if prev_price_trough_idx != -1:
                    # Check Price LL
                    if df['low'].iloc[price_trough_idx] < df['low'].iloc[prev_price_trough_idx]:
                        # Check Indicator HL
                        if df[ind].iloc[price_trough_idx] > df[ind].iloc[prev_price_trough_idx]:
                            signals.append(f"Bullish {ind.upper()} Divergence")
                            
        return signals

    @staticmethod
    def generate_technical_summary(df):
        """
        Professional scalping-focused technical analysis.
        FIXED: Uses EMA for trend, VWAP for support/resistance.
        """
        last = df.iloc[-1]
        signals = []
        score = 0
        
        # Ensure EMA trend is calculated
        if 'ema_trend' not in df.columns:
            df = QuantLogic.calculate_ema_trend(df)
            last = df.iloc[-1]
        
        # 1. Primary Trend Filter (EMA-based, not VWAP)
        is_bull_trend = last['ema_trend']
        is_bear_trend = not last['ema_trend']
        
        if is_bull_trend:
            signals.append("EMA 21 > EMA 50 (Bull Trend)")
            score += 2
        else:
            signals.append("EMA 21 < EMA 50 (Bear Trend)")
            score -= 2
        
        # 1b. VWAP as Support/Resistance (not trend)
        if last['close'] > last['vwap']:
            if is_bull_trend:
                signals.append("Price > VWAP (Above Support)")
                score += 1
        else:
            if is_bear_trend:
                signals.append("Price < VWAP (Below Resistance)")
                score -= 1
        
        # 1c. Funding Pressure (if available)
        if 'funding_pressure' in df.columns:
            funding_status = last['funding_pressure']
            if 'Short Squeeze Risk' in funding_status:
                signals.append(f"{funding_status}")
                score += 2
            elif 'Long Squeeze Risk' in funding_status:
                signals.append(f"{funding_status}")
                score -= 2
            elif funding_status != 'Neutral':
                signals.append(f"{funding_status}")
            
        # 0. Divergence Check (Only trend-aligned divergences count)
        div_signals = QuantLogic.detect_divergences(df)
        for div in div_signals:
            if "Bullish" in div and is_bull_trend:
                signals.append(f"{div} (Trend Aligned)")
                score += 2
            elif "Bearish" in div and is_bear_trend:
                signals.append(f"{div} (Trend Aligned)")
                score -= 2
            else:
                signals.append(f"{div} (Counter-Trend, Ignored)")
        
        # 2. RSI Analysis (Regime Filtered)
        if last['rsi'] < 30 and is_bull_trend:
            signals.append("RSI Oversold in Bull Trend (Pullback Long)")
            score += 2
        elif last['rsi'] > 70 and is_bear_trend:
            signals.append("RSI Overbought in Bear Trend (Pullback Short)")
            score -= 2
        # Ignored states: RSI > 70 in Bull Trend (expected), RSI < 30 in Bear Trend (expected)
        
        # 3. Money Flow (CMF)
        if last['cmf'] > 0.05:
            signals.append("CMF Positive (Institutional Inflow)")
            score += 1 if is_bull_trend else 0
        elif last['cmf'] < -0.05:
            signals.append("CMF Negative (Institutional Outflow)")
            score -= 1 if is_bear_trend else 0
            
        # 4. MACD Momentum
        if last['macd'] > last['macd_signal']:
            signals.append("MACD Bullish Momentum")
            score += 1 if is_bull_trend else 0
        else:
            signals.append("MACD Bearish Momentum")
            score -= 1 if is_bear_trend else 0
            
        # 5. Bollinger Bands (Regime Filtered)
        if last['close'] < last['bb_lower'] and is_bull_trend:
            signals.append("Price at Lower BB in Bull Trend (Buy Zone)")
            score += 1
        elif last['close'] > last['bb_upper'] and is_bear_trend:
            signals.append("Price at Upper BB in Bear Trend (Sell Zone)")
            score -= 1
            
        # 6. Stochastic RSI (Regime Filtered)
        if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d'] and is_bull_trend:
            signals.append("Stoch RSI Oversold Push in Bull Trend")
            score += 1
        elif last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d'] and is_bear_trend:
            signals.append("Stoch RSI Overbought Rejection in Bear Trend")
            score -= 1

        # Determine Overall Sentiment
        if score >= 4:
            sentiment = "STRONG BULLISH 🚀"
            color = "green"
        elif score >= 1:
            sentiment = "BULLISH 🟢"
            color = "lightgreen"
        elif score <= -4:
            sentiment = "STRONG BEARISH 🩸"
            color = "red"
        elif score <= -1:
            sentiment = "BEARISH 🔴"
            color = "salmon"
        else:
            sentiment = "NEUTRAL (CHOP) ⚖️"
            color = "gray"
            
        unique_signals = []
        seen = set()
        for s in signals:
            if s not in seen:
                unique_signals.append(s)
                seen.add(s)

        return {
            "sentiment": sentiment,
            "score": score,
            "signals": unique_signals,
            "color": color
        }
