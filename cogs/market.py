"""
Market Analysis Cog — !analyze [symbol], !chart [symbol]
Fetches OHLCV data via ccxt and generates sarcastic AI commentary with Gemini.
"""

import io
import os
import logging
from datetime import datetime, timezone

import ccxt.async_support as ccxt
import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from google.genai import types

import matplotlib
matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger("quant_sniper.market")

# ── Gemini system prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """你是「量化狙擊手」，一位尖酸刻薄、幽默風趣的華爾街老手交易員。
你的任務是根據提供的 OHLCV（開盤、最高、最低、收盤、成交量）數據，
給出簡短但犀利的市場分析。

規則：
1. 使用繁體中文回覆。
2. 語氣要像一位見過無數韭菜的老油條，帶著黑色幽默。
3. 回覆格式必須嚴格如下（不要加任何多餘標記）：

趨勢：[看漲 🟢 / 看跌 🔴 / 盤整 ⚪]
分析：[2-3 句犀利評論]
建議：[一句話，可以搞笑但要有道理]

4. 不要提供具體的買賣建議或價格目標，這只是娛樂性質的分析。
"""


class Market(commands.Cog, name="📊 市場分析"):
    """Real-time market analysis powered by AI."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.exchange = ccxt.binance({"enableRateLimit": True})

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set in .env")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    async def cog_unload(self) -> None:
        await self.exchange.close()

    # ── Helper: fetch OHLCV ──────────────────────────────────────────
    async def _fetch_ohlcv(self, symbol: str, limit: int = 24) -> list:
        """Fetch 1h candles for *symbol*."""
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe="1h", limit=limit)
        return ohlcv

    @staticmethod
    def _format_ohlcv(ohlcv: list, symbol: str) -> str:
        """Format OHLCV list into a readable string for the LLM."""
        lines = [f"交易對：{symbol}", "時間 | 開盤 | 最高 | 最低 | 收盤 | 成交量"]
        for candle in ohlcv:
            ts = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc).strftime(
                "%m-%d %H:%M"
            )
            o, h, l, c, v = candle[1:]
            lines.append(f"{ts} | {o:.2f} | {h:.2f} | {l:.2f} | {c:.2f} | {v:.2f}")
        return "\n".join(lines)

    # ── Helper: technical indicators ─────────────────────────────────
    @staticmethod
    def _calc_sma(closes: list[float], period: int) -> list[float | None]:
        """Simple Moving Average."""
        sma = []
        for i in range(len(closes)):
            if i < period - 1:
                sma.append(None)
            else:
                sma.append(sum(closes[i - period + 1 : i + 1]) / period)
        return sma

    @staticmethod
    def _calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
        """Relative Strength Index."""
        rsi = [None] * period
        gains, losses = [], []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))

        if len(gains) < period:
            return [None] * len(closes)

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))

        return rsi

    # ── Command: /analyze ────────────────────────────────────────────
    @commands.hybrid_command(name="analyze", aliases=["a", "分析"])
    @app_commands.describe(symbol="幣種或交易對，例如 BNB 或 BTC/USDT")
    async def analyze(self, ctx: commands.Context, symbol: str = "BNB/USDT") -> None:
        """分析指定交易對的市場走勢（預設 BNB/USDT）。"""
        symbol = symbol.upper()
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"

        async with ctx.typing():
            # 1) Fetch market data
            try:
                ohlcv = await self._fetch_ohlcv(symbol)
            except ccxt.BadSymbol:
                await ctx.send(f"❌ 找不到交易對 `{symbol}`，請確認格式（例：BNB/USDT）。")
                return
            except Exception as exc:
                logger.error("OHLCV fetch error for %s: %s", symbol, exc)
                await ctx.send("❌ 無法取得市場數據，請稍後再試。")
                return

            if not ohlcv:
                await ctx.send(f"⚠️ `{symbol}` 沒有可用的 K 線數據。")
                return

            current_price = ohlcv[-1][4]  # latest close

            # 2) Generate AI commentary
            data_str = self._format_ohlcv(ohlcv, symbol)
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=data_str,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                    ),
                )
                commentary = response.text.strip()
            except Exception as exc:
                logger.error("Gemini API error: %s", exc)
                commentary = "（AI 分析暫時無法取得，可能是被市場嚇到了 😱）"

            # 3) Parse trend from commentary
            if "看漲" in commentary or "🟢" in commentary:
                trend = "🟢 看漲 Bullish"
                embed_color = 0x00E676
            elif "看跌" in commentary or "🔴" in commentary:
                trend = "🔴 看跌 Bearish"
                embed_color = 0xFF1744
            else:
                trend = "⚪ 盤整 Sideways"
                embed_color = 0x90A4AE

            # 4) Build embed
            embed = discord.Embed(
                title=f"📊 {symbol} 市場分析",
                color=embed_color,
                timestamp=datetime.now(tz=timezone.utc),
            )
            embed.add_field(name="💰 當前價格", value=f"`${current_price:,.4f}`", inline=True)
            embed.add_field(name="📈 趨勢判斷", value=trend, inline=True)
            embed.add_field(name="🤖 AI 狙擊手點評", value=commentary, inline=False)
            embed.set_footer(text="⚠️ 僅供娛樂，不構成投資建議 | Quant Sniper Bot")

            await ctx.send(embed=embed)

    # ── Command: /chart ──────────────────────────────────────────────
    @commands.hybrid_command(name="chart", aliases=["c", "圖表"])
    @app_commands.describe(symbol="幣種或交易對，例如 BNB 或 BTC/USDT")
    async def chart(self, ctx: commands.Context, symbol: str = "BNB/USDT") -> None:
        """生成價格走勢圖 + 技術指標（SMA、RSI）。"""
        symbol = symbol.upper()
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"

        async with ctx.typing():
            try:
                ohlcv = await self._fetch_ohlcv(symbol, limit=72)  # 3 days of 1h data
            except ccxt.BadSymbol:
                await ctx.send(f"❌ 找不到交易對 `{symbol}`，請確認格式（例：BNB/USDT）。")
                return
            except Exception as exc:
                logger.error("Chart OHLCV fetch error for %s: %s", symbol, exc)
                await ctx.send("❌ 無法取得市場數據，請稍後再試。")
                return

            if not ohlcv or len(ohlcv) < 20:
                await ctx.send(f"⚠️ `{symbol}` 數據不足以生成圖表。")
                return

            # Extract data
            timestamps = [datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc) for c in ohlcv]
            closes = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            sma20 = self._calc_sma(closes, 20)
            rsi = self._calc_rsi(closes, 14)

            current_price = closes[-1]
            rsi_current = rsi[-1]

            # ── Build chart ──────────────────────────────────────────
            fig, (ax_price, ax_rsi) = plt.subplots(
                2, 1, figsize=(12, 7), height_ratios=[3, 1],
                gridspec_kw={"hspace": 0.08},
            )
            fig.patch.set_facecolor("#1a1a2e")

            # Price + SMA
            ax_price.set_facecolor("#16213e")
            ax_price.plot(timestamps, closes, color="#00E676", linewidth=1.5, label="收盤價")
            sma_vals = [(t, v) for t, v in zip(timestamps, sma20) if v is not None]
            if sma_vals:
                ax_price.plot(
                    [s[0] for s in sma_vals], [s[1] for s in sma_vals],
                    color="#FFD600", linewidth=1, linestyle="--", label="SMA 20",
                )
            ax_price.fill_between(timestamps, closes, min(closes), alpha=0.1, color="#00E676")
            # Auto-scale Y axis to data range with 5% padding
            price_min, price_max = min(closes), max(closes)
            price_margin = (price_max - price_min) * 0.05 or price_max * 0.01
            ax_price.set_ylim(price_min - price_margin, price_max + price_margin)
            ax_price.set_title(
                f"📊 {symbol}  |  ${current_price:,.4f}",
                color="white", fontsize=14, fontweight="bold", pad=12,
            )
            ax_price.legend(loc="upper left", fontsize=8, facecolor="#16213e", edgecolor="#333",
                            labelcolor="white")
            ax_price.tick_params(colors="white", labelsize=8)
            ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            ax_price.tick_params(axis="x", labelbottom=False)
            ax_price.grid(color="#333", alpha=0.5)
            for spine in ax_price.spines.values():
                spine.set_color("#333")

            # RSI
            ax_rsi.set_facecolor("#16213e")
            rsi_vals = [(t, v) for t, v in zip(timestamps, rsi) if v is not None]
            if rsi_vals:
                rsi_times = [r[0] for r in rsi_vals]
                rsi_data = [r[1] for r in rsi_vals]
                ax_rsi.plot(rsi_times, rsi_data, color="#BB86FC", linewidth=1.2)
                ax_rsi.axhline(y=70, color="#FF1744", linewidth=0.8, linestyle="--", alpha=0.7)
                ax_rsi.axhline(y=30, color="#00E676", linewidth=0.8, linestyle="--", alpha=0.7)
                ax_rsi.fill_between(rsi_times, rsi_data, 70,
                                     where=[v > 70 for v in rsi_data], alpha=0.2, color="#FF1744")
                ax_rsi.fill_between(rsi_times, rsi_data, 30,
                                     where=[v < 30 for v in rsi_data], alpha=0.2, color="#00E676")
            ax_rsi.set_ylabel("RSI", color="white", fontsize=9)
            ax_rsi.set_ylim(0, 100)
            ax_rsi.tick_params(colors="white", labelsize=8)
            ax_rsi.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            fig.autofmt_xdate(rotation=30)
            ax_rsi.grid(color="#333", alpha=0.5)
            for spine in ax_rsi.spines.values():
                spine.set_color("#333")

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
            buf.seek(0)
            plt.close(fig)

            # RSI status text
            if rsi_current is not None:
                if rsi_current > 70:
                    rsi_text = f"🔴 RSI {rsi_current:.1f}（超買區）"
                elif rsi_current < 30:
                    rsi_text = f"🟢 RSI {rsi_current:.1f}（超賣區）"
                else:
                    rsi_text = f"⚪ RSI {rsi_current:.1f}（中性）"
            else:
                rsi_text = "數據不足"

            embed = discord.Embed(
                title=f"📈 {symbol} 技術分析圖",
                color=0x448AFF,
                timestamp=datetime.now(tz=timezone.utc),
            )
            embed.add_field(name="💰 當前價格", value=f"`${current_price:,.4f}`", inline=True)
            embed.add_field(name="📊 RSI(14)", value=rsi_text, inline=True)
            embed.set_image(url="attachment://chart.png")
            embed.set_footer(text="1H 時間框架 · SMA 20 · RSI 14 | Quant Sniper Bot")

            await ctx.send(embed=embed, file=discord.File(buf, filename="chart.png"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Market(bot))

