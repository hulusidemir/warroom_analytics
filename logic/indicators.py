import numpy as np
import pandas as pd

class QuantLogic:
    
    @staticmethod
    def calculate_vwap(df):
        """Daily Anchored VWAP (Resets every day)"""
        df['date'] = df['timestamp'].dt.date
        
        def calc_vwap_group(group):
            v = group['volume']
            tp = (group['high'] + group['low'] + group['close']) / 3
            return (tp * v).cumsum() / v.cumsum()
            
        df['vwap'] = df.groupby('date', group_keys=False).apply(calc_vwap_group)
        return df

    @staticmethod
    def calculate_cvd(df):
        """
        Calculates Precise Cumulative Volume Delta (CVD) anchored to the daily session.
        If Taker Data is missing, CVD returns None.
        """
        if df['taker_buy_vol'].isnull().all():
            df['cvd'] = 0
            return df

        df['taker_buy_vol'] = df['taker_buy_vol'].fillna(df['volume'] * 0.5) # Fallback to 50% only if sporadic missing data, but base logic prevents this.
        df['taker_sell_vol'] = df['volume'] - df['taker_buy_vol']
        df['delta'] = df['taker_buy_vol'] - df['taker_sell_vol']
        
        # Session Anchored CVD (Reset at 00:00 UTC)
        df['date'] = df['timestamp'].dt.date
        
        def calc_cvd_group(group):
            return group['delta'].cumsum()
            
        df['cvd'] = df.groupby('date', group_keys=False).apply(calc_cvd_group)
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
            
        # Calculate changes/deltas
        df['price_change'] = df['close'] - df['open']
        df['oi_change_pct'] = df['oi'].pct_change() * 100
        
        # Dynamic Threshold (0.5 * ATR for trend detection, prevents choppy regime switches)
        df['bull_trend'] = df['price_change'] > (0.5 * df['atr'])
        df['bear_trend'] = df['price_change'] < -(0.5 * df['atr'])
        
        # OI Threshold (At least 0.2% change to be considered institutional involvement)
        oi_thresh = 0.2 
        
        if 'delta' not in df.columns:
            df['delta'] = 0

        conditions = [
            (df['bull_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['delta'] > 0), # Strong Long Buildup
            (df['bull_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['delta'] <= 0), # Absorption Long Buildup
            
            (df['bull_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['delta'] > 0), # Short Covering (Aggressive)
            (df['bull_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['delta'] <= 0), # Short Covering (Passive)
            
            (df['bear_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['delta'] < 0), # Strong Short Buildup
            (df['bear_trend']) & (df['oi_change_pct'] > oi_thresh) & (df['delta'] >= 0), # Absorption Short Buildup
            
            (df['bear_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['delta'] < 0), # Long Liquidation (Aggressive)
            (df['bear_trend']) & (df['oi_change_pct'] < -oi_thresh) & (df['delta'] >= 0)  # Long Liquidation (Passive)
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
        
        df['regime'] = np.select(conditions, choices, default='Neutral')
        return df

    @staticmethod
    def detect_sfp(df):
        """
        Real Liquidity Hunt Detector (SFP).
        Calculates Prior Day High/Low (PDH/PDL) and detects sweeps.
        """
        df['sfp_signal'] = None
        
        # Group by day to find daily highs and lows
        df['date'] = df['timestamp'].dt.date
        daily_stats = df.groupby('date').agg({'high': 'max', 'low': 'min'}).reset_index()
        daily_stats['PDH'] = daily_stats['high'].shift(1)  # Previous Day High
        daily_stats['PDL'] = daily_stats['low'].shift(1)   # Previous Day Low
        
        # Merge back to original dataframe on date
        df = df.merge(daily_stats[['date', 'PDH', 'PDL']], on='date', how='left')
        
        # Bullish SFP: Price wicks below PDL but closes above it
        bull_sfp = (df['low'] < df['PDL']) & (df['close'] > df['PDL'])
        
        # Bearish SFP: Price wicks above PDH but closes below it
        bear_sfp = (df['high'] > df['PDH']) & (df['close'] < df['PDH'])
        
        df.loc[bull_sfp, 'sfp_signal'] = 'Bullish SFP (PDL Sweep) 🚀'
        df.loc[bear_sfp, 'sfp_signal'] = 'Bearish SFP (PDH Sweep) 🔻'
        
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
        """Money Flow Index (Volume-weighted RSI)"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        # Positive/Negative Money Flow
        # We need to compare typical price with previous typical price
        tp_diff = typical_price.diff()
        
        pos_flow = pd.Series(0.0, index=df.index)
        neg_flow = pd.Series(0.0, index=df.index)
        
        pos_flow[tp_diff > 0] = money_flow[tp_diff > 0]
        neg_flow[tp_diff < 0] = money_flow[tp_diff < 0]
        
        # Rolling sums
        pos_mf = pos_flow.rolling(window=period).sum()
        neg_mf = neg_flow.rolling(window=period).sum()
        
        mfi_ratio = pos_mf / neg_mf
        df['mfi'] = 100 - (100 / (1 + mfi_ratio))
        return df

    @staticmethod
    def calculate_obv(df):
        """On-Balance Volume"""
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return df

    @staticmethod
    def calculate_cmf(df, period=20):
        """Chaikin Money Flow"""
        # Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
        mf_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        mf_volume = mf_multiplier * df['volume']
        
        df['cmf'] = mf_volume.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
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
        Generates a professional regime-filtered technical analysis summary.
        Oscillators are ignored if they contradict the main trend (VWAP).
        """
        last = df.iloc[-1]
        signals = []
        score = 0
        
        # 1. Primary Trend Filter (Anchor)
        is_bull_trend = last['close'] > last['vwap']
        is_bear_trend = last['close'] < last['vwap']
        
        if is_bull_trend:
            signals.append("Price > VWAP (Primary Bull Trend)")
            score += 2
        else:
            signals.append("Price < VWAP (Primary Bear Trend)")
            score -= 2
            
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
