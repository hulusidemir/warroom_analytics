import numpy as np
import pandas as pd

class QuantLogic:
    
    @staticmethod
    def calculate_vwap(df):
        """Anchored VWAP (resets at start of DataFrame for this view)"""
        v = df['volume'].values
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (tp * v).cumsum() / v.cumsum()
        return df

    @staticmethod
    def calculate_cvd(df):
        """
        Calculates Precise Cumulative Volume Delta (CVD).
        Formula: Delta = Buy_Aggressors - Sell_Aggressors
        """
        # 1. Derive Taker Sell Volume
        df['taker_sell_vol'] = df['volume'] - df['taker_buy_vol']
        
        # 2. Calculate Net Delta per candle
        df['delta'] = df['taker_buy_vol'] - df['taker_sell_vol']
        
        # 3. Cumulative Sum for the CVD Line
        df['cvd'] = df['delta'].cumsum()
        
        return df

    @staticmethod
    def identify_oi_regime(df):
        """
        Classifies the market state based on Price and OI Delta.
        """
        df['price_change'] = df['close'].diff()
        df['oi_change'] = df['oi'].diff()

        conditions = [
            (df['price_change'] > 0) & (df['oi_change'] > 0), # Long Buildup
            (df['price_change'] > 0) & (df['oi_change'] < 0), # Short Covering
            (df['price_change'] < 0) & (df['oi_change'] > 0), # Short Buildup
            (df['price_change'] < 0) & (df['oi_change'] < 0)  # Long Liquidation
        ]
        choices = ['Long Buildup 🟢', 'Short Covering 👻', 'Short Buildup 🔴', 'Long Liq 🩸']
        
        df['regime'] = np.select(conditions, choices, default='Neutral')
        return df

    @staticmethod
    def detect_sfp(df, window=5):
        """
        Swing Failure Pattern (Liquidity Hunt) Detector.
        """
        df['sfp_signal'] = None
        
        # Bullish SFP: Low breaks prev N-lows but closes above
        rolling_min = df['low'].rolling(window=window).min().shift(1)
        bull_sfp = (df['low'] < rolling_min) & (df['close'] > rolling_min)
        
        # Bearish SFP: High breaks prev N-highs but closes below
        rolling_max = df['high'].rolling(window=window).max().shift(1)
        bear_sfp = (df['high'] > rolling_max) & (df['close'] < rolling_max)
        
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
        Generates a professional technical analysis summary based on calculated indicators.
        Returns a dictionary with signal details and overall sentiment.
        """
        last = df.iloc[-1]
        signals = []
        score = 0 # Positive = Bullish, Negative = Bearish
        
        # 0. Divergence Check
        div_signals = QuantLogic.detect_divergences(df)
        for div in div_signals:
            signals.append(div)
            if "Bullish" in div: score += 2
            if "Bearish" in div: score -= 2
        
        # 1. VWAP Analysis
        if last['close'] > last['vwap']:
            signals.append("Price > VWAP (Bullish Trend)")
            score += 1
        else:
            signals.append("Price < VWAP (Bearish Trend)")
            score -= 1
            
        # 2. RSI Analysis
        if last['rsi'] < 30:
            signals.append("RSI Oversold (Bullish Reversal Potential)")
            score += 2
        elif last['rsi'] > 70:
            signals.append("RSI Overbought (Bearish Reversal Potential)")
            score -= 2
        
        # 3. Money Flow (CMF)
        if last['cmf'] > 0.05:
            signals.append("CMF Positive (Inflow)")
            score += 1
        elif last['cmf'] < -0.05:
            signals.append("CMF Negative (Outflow)")
            score -= 1
            
        # 4. MACD
        if last['macd'] > last['macd_signal']:
            signals.append("MACD Bullish Crossover")
            score += 1
        else:
            signals.append("MACD Bearish Crossover")
            score -= 1
            
        # 5. Bollinger Bands
        if last['close'] < last['bb_lower']:
            signals.append("Price Below BB Lower (Oversold)")
            score += 1
        elif last['close'] > last['bb_upper']:
            signals.append("Price Above BB Upper (Overbought)")
            score -= 1
            
        # 6. Stochastic RSI
        if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d']:
            signals.append("Stoch RSI Oversold & Crossing Up")
            score += 1
        elif last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d']:
            signals.append("Stoch RSI Overbought & Crossing Down")
            score -= 1

        # Determine Overall Sentiment
        if score >= 3:
            sentiment = "STRONG BULLISH 🚀"
            color = "green"
        elif score >= 1:
            sentiment = "BULLISH 🟢"
            color = "lightgreen"
        elif score <= -3:
            sentiment = "STRONG BEARISH 🩸"
            color = "red"
        elif score <= -1:
            sentiment = "BEARISH 🔴"
            color = "salmon"
        else:
            sentiment = "NEUTRAL ⚖️"
            color = "gray"
            
        # Remove duplicates while preserving order
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
