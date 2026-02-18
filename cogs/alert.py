"""
Price Alert Cog — !alert [symbol] [price]
Allows users to set price alerts and get notified when conditions are met.
"""

import logging
from datetime import datetime, timezone

import ccxt.async_support as ccxt
import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("quant_sniper.alert")


class PriceAlert:
    """A single price alert."""

    __slots__ = ("user_id", "channel_id", "symbol", "target_price", "direction", "created_at")

    def __init__(
        self,
        user_id: int,
        channel_id: int,
        symbol: str,
        target_price: float,
        direction: str,  # "above" or "below"
    ) -> None:
        self.user_id = user_id
        self.channel_id = channel_id
        self.symbol = symbol
        self.target_price = target_price
        self.direction = direction
        self.created_at = datetime.now(tz=timezone.utc)


class Alert(commands.Cog, name="🔔 價格警報"):
    """Set price alerts and get notified in Discord."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.exchange = ccxt.binance({"enableRateLimit": True})
        self.alerts: list[PriceAlert] = []
        self.check_alerts.start()

    async def cog_unload(self) -> None:
        self.check_alerts.cancel()
        await self.exchange.close()

    # ── Background task: check alerts every 30 seconds ───────────────
    @tasks.loop(seconds=30)
    async def check_alerts(self) -> None:
        if not self.alerts:
            return

        # Group alerts by symbol to minimize API calls
        symbols = set(a.symbol for a in self.alerts)
        prices: dict[str, float] = {}

        for symbol in symbols:
            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                prices[symbol] = ticker["last"]
            except Exception as exc:
                logger.error("Alert price fetch error for %s: %s", symbol, exc)

        triggered: list[PriceAlert] = []
        remaining: list[PriceAlert] = []

        for alert in self.alerts:
            price = prices.get(alert.symbol)
            if price is None:
                remaining.append(alert)
                continue

            hit = False
            if alert.direction == "above" and price >= alert.target_price:
                hit = True
            elif alert.direction == "below" and price <= alert.target_price:
                hit = True

            if hit:
                triggered.append(alert)
            else:
                remaining.append(alert)

        self.alerts = remaining

        # Send notifications
        for alert in triggered:
            try:
                channel = self.bot.get_channel(alert.channel_id)
                if channel is None:
                    continue

                price = prices[alert.symbol]
                direction_text = "突破 ⬆️" if alert.direction == "above" else "跌破 ⬇️"
                emoji = "🟢" if alert.direction == "above" else "🔴"

                embed = discord.Embed(
                    title=f"🔔 價格警報觸發！",
                    color=0x00E676 if alert.direction == "above" else 0xFF1744,
                    timestamp=datetime.now(tz=timezone.utc),
                )
                embed.add_field(
                    name="📊 交易對",
                    value=f"`{alert.symbol}`",
                    inline=True,
                )
                embed.add_field(
                    name=f"{emoji} 條件",
                    value=f"{direction_text} `${alert.target_price:,.4f}`",
                    inline=True,
                )
                embed.add_field(
                    name="💰 當前價格",
                    value=f"`${price:,.4f}`",
                    inline=True,
                )
                embed.set_footer(text="Quant Sniper — 價格警報")

                user = await self.bot.fetch_user(alert.user_id)
                await channel.send(f"{user.mention} 你的警報響了！", embed=embed)
            except Exception as exc:
                logger.error("Failed to send alert notification: %s", exc)

    @check_alerts.before_loop
    async def before_check(self) -> None:
        await self.bot.wait_until_ready()

    # ── Command: /alert ──────────────────────────────────────────────
    @commands.hybrid_command(name="alert", aliases=["警報"])
    @app_commands.describe(symbol="幣種或交易對，例如 BNB 或 BTC/USDT", target_price="目標價格")
    async def set_alert(
        self,
        ctx: commands.Context,
        symbol: str = "BNB/USDT",
        target_price: float = 0.0,
    ) -> None:
        """設定價格警報。用法：/alert BNB/USDT 700"""
        if target_price <= 0:
            await ctx.send(
                "📖 **用法：** `/alert <交易對> <目標價格>`\n"
                "📌 **範例：**\n"
                "　　`/alert BNB/USDT 700` — BNB 漲到 700 時通知\n"
                "　　`/alert BTC/USDT 90000` — BTC 漲到 90000 時通知\n"
                "💡 會自動判斷是「突破」還是「跌破」警報！"
            )
            return

        symbol = symbol.upper()
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"

        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            current_price = ticker["last"]
        except ccxt.BadSymbol:
            await ctx.send(f"❌ 找不到交易對 `{symbol}`，請確認格式（例：BNB/USDT）。")
            return
        except Exception as exc:
            logger.error("Alert ticker fetch error: %s", exc)
            await ctx.send("❌ 無法取得當前價格，請稍後再試。")
            return

        # Determine direction
        if target_price > current_price:
            direction = "above"
            direction_text = "突破 ⬆️"
            emoji = "🟢"
            color = 0x00E676
        else:
            direction = "below"
            direction_text = "跌破 ⬇️"
            emoji = "🔴"
            color = 0xFF1744

        alert = PriceAlert(
            user_id=ctx.author.id,
            channel_id=ctx.channel.id,
            symbol=symbol,
            target_price=target_price,
            direction=direction,
        )
        self.alerts.append(alert)

        embed = discord.Embed(
            title="🔔 價格警報已設定！",
            color=color,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="📊 交易對", value=f"`{symbol}`", inline=True)
        embed.add_field(name="💰 當前價格", value=f"`${current_price:,.4f}`", inline=True)
        embed.add_field(
            name=f"{emoji} 警報條件",
            value=f"{direction_text} `${target_price:,.4f}`",
            inline=True,
        )
        embed.set_footer(text=f"每 30 秒檢查一次 | 你目前有 {len([a for a in self.alerts if a.user_id == ctx.author.id])} 個警報")

        await ctx.send(embed=embed)

    # ── Command: /alerts ─────────────────────────────────────────────
    @commands.hybrid_command(name="alerts", aliases=["我的警報"])
    async def list_alerts(self, ctx: commands.Context) -> None:
        """查看你設定的所有價格警報。"""
        user_alerts = [a for a in self.alerts if a.user_id == ctx.author.id]

        if not user_alerts:
            await ctx.send("📭 你目前沒有設定任何價格警報。用 `!alert <交易對> <價格>` 來設定！")
            return

        embed = discord.Embed(
            title=f"🔔 {ctx.author.display_name} 的價格警報",
            color=0x448AFF,
            timestamp=datetime.now(tz=timezone.utc),
        )

        lines = []
        for i, alert in enumerate(user_alerts, 1):
            direction_text = "⬆️ 突破" if alert.direction == "above" else "⬇️ 跌破"
            lines.append(
                f"`#{i}` **{alert.symbol}** — {direction_text} `${alert.target_price:,.4f}`"
            )

        embed.add_field(name="警報列表", value="\n".join(lines), inline=False)
        embed.set_footer(text="用 !clearalerts 清除所有警報 | Quant Sniper")

        await ctx.send(embed=embed)

    # ── Command: /clearalerts ────────────────────────────────────────
    @commands.hybrid_command(name="clearalerts", aliases=["清除警報"])
    async def clear_alerts(self, ctx: commands.Context) -> None:
        """清除你所有的價格警報。"""
        before = len(self.alerts)
        self.alerts = [a for a in self.alerts if a.user_id != ctx.author.id]
        removed = before - len(self.alerts)

        if removed == 0:
            await ctx.send("📭 你沒有任何警報可以清除。")
        else:
            await ctx.send(f"🗑️ 已清除 **{removed}** 個警報！")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Alert(bot))
