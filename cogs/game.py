"""
Mock Trading Game Cog — !buy, !sell, !portfolio
Paper trading system backed by SQLite with real-time ccxt prices.
"""

import os
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import ccxt.async_support as ccxt
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("quant_sniper.game")

INITIAL_BALANCE = 10_000.0  # USDT
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "trading.db"


class TradingDB:
    """Thin wrapper around SQLite for the paper trading ledger."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id   TEXT PRIMARY KEY,
                    balance   REAL NOT NULL DEFAULT 10000.0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS holdings (
                    user_id   TEXT NOT NULL,
                    symbol    TEXT NOT NULL,
                    quantity  REAL NOT NULL DEFAULT 0.0,
                    avg_price REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (user_id, symbol),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                """
            )

    # ── User helpers ─────────────────────────────────────────────────
    def ensure_user(self, user_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT INTO users (user_id, balance, created_at) VALUES (?, ?, ?)",
                (user_id, INITIAL_BALANCE, now),
            )
        return {"user_id": user_id, "balance": INITIAL_BALANCE, "created_at": now}

    def get_balance(self, user_id: str) -> float:
        row = self.conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["balance"] if row else 0.0

    def update_balance(self, user_id: str, delta: float) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (delta, user_id),
            )

    # ── Holdings helpers ─────────────────────────────────────────────
    def get_holding(self, user_id: str, symbol: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM holdings WHERE user_id = ? AND symbol = ?",
            (user_id, symbol),
        ).fetchone()
        return dict(row) if row else None

    def get_all_holdings(self, user_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM holdings WHERE user_id = ? AND quantity > 0",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_holding(
        self, user_id: str, symbol: str, quantity: float, avg_price: float
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO holdings (user_id, symbol, quantity, avg_price)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, symbol)
                DO UPDATE SET quantity = ?, avg_price = ?
                """,
                (user_id, symbol, quantity, avg_price, quantity, avg_price),
            )

    def delete_holding(self, user_id: str, symbol: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM holdings WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
            )


class Game(commands.Cog, name="🎮 模擬交易"):
    """Paper trading game — start with $10,000 USDT and see how you do!"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = TradingDB()
        self.exchange = ccxt.binance({"enableRateLimit": True})

    async def cog_unload(self) -> None:
        await self.exchange.close()

    # ── Price helper ─────────────────────────────────────────────────
    async def _get_price(self, symbol: str) -> float:
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker["last"]

    # ── Command: /buy ────────────────────────────────────────────────
    @commands.hybrid_command(name="buy", aliases=["買"])
    @app_commands.describe(symbol="幣種或交易對，例如 BNB 或 BTC/USDT", amount="花費的 USDT 金額")
    async def buy(
        self, ctx: commands.Context, symbol: str, amount: float
    ) -> None:
        """買入代幣。用法：/buy BNB/USDT 100（花 100 USDT 買入）"""
        symbol = symbol.upper()
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"
        user_id = str(ctx.author.id)
        self.db.ensure_user(user_id)

        if amount <= 0:
            await ctx.send("❌ 金額必須大於 0。")
            return

        async with ctx.typing():
            # Fetch real-time price
            try:
                price = await self._get_price(symbol)
            except ccxt.BadSymbol:
                await ctx.send(f"❌ 找不到交易對 `{symbol}`，請確認格式（例：BNB/USDT）。")
                return
            except Exception as exc:
                logger.error("Price fetch error for %s: %s", symbol, exc)
                await ctx.send("❌ 無法取得即時報價，請稍後再試。")
                return

            # Check balance
            balance = self.db.get_balance(user_id)
            if amount > balance:
                await ctx.send(
                    f"❌ 餘額不足！目前餘額：`${balance:,.2f}` USDT，"
                    f"欲花費：`${amount:,.2f}` USDT。"
                )
                return

            qty_bought = amount / price

            # Update holding (weighted average price)
            existing = self.db.get_holding(user_id, symbol)
            if existing:
                old_qty = existing["quantity"]
                old_avg = existing["avg_price"]
                new_qty = old_qty + qty_bought
                new_avg = ((old_avg * old_qty) + (price * qty_bought)) / new_qty
            else:
                new_qty = qty_bought
                new_avg = price

            self.db.upsert_holding(user_id, symbol, new_qty, new_avg)
            self.db.update_balance(user_id, -amount)

        embed = discord.Embed(
            title="✅ 買入成功",
            color=0x00E676,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="交易對", value=f"`{symbol}`", inline=True)
        embed.add_field(name="成交價", value=f"`${price:,.4f}`", inline=True)
        embed.add_field(name="買入數量", value=f"`{qty_bought:,.6f}`", inline=True)
        embed.add_field(name="花費", value=f"`${amount:,.2f}` USDT", inline=True)
        embed.add_field(
            name="剩餘餘額",
            value=f"`${self.db.get_balance(user_id):,.2f}` USDT",
            inline=True,
        )
        embed.set_footer(text="Quant Sniper — 模擬交易")
        await ctx.send(embed=embed)

    # ── Command: /sell ───────────────────────────────────────────────
    @commands.hybrid_command(name="sell", aliases=["賣"])
    @app_commands.describe(symbol="幣種或交易對，例如 BNB 或 BTC/USDT", quantity="要賣出的數量")
    async def sell(
        self, ctx: commands.Context, symbol: str, quantity: float
    ) -> None:
        """賣出代幣。用法：/sell BNB/USDT 0.5（賣出 0.5 個代幣）"""
        symbol = symbol.upper()
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"
        user_id = str(ctx.author.id)
        self.db.ensure_user(user_id)

        if quantity <= 0:
            await ctx.send("❌ 數量必須大於 0。")
            return

        holding = self.db.get_holding(user_id, symbol)
        if not holding or holding["quantity"] < quantity:
            held = holding["quantity"] if holding else 0
            await ctx.send(
                f"❌ 持倉不足！目前持有 `{symbol}`：`{held:,.6f}`，"
                f"欲賣出：`{quantity:,.6f}`。"
            )
            return

        async with ctx.typing():
            try:
                price = await self._get_price(symbol)
            except ccxt.BadSymbol:
                await ctx.send(f"❌ 找不到交易對 `{symbol}`。")
                return
            except Exception as exc:
                logger.error("Price fetch error for %s: %s", symbol, exc)
                await ctx.send("❌ 無法取得即時報價，請稍後再試。")
                return

            proceeds = quantity * price
            remaining_qty = holding["quantity"] - quantity

            if remaining_qty < 1e-9:
                self.db.delete_holding(user_id, symbol)
            else:
                self.db.upsert_holding(
                    user_id, symbol, remaining_qty, holding["avg_price"]
                )

            self.db.update_balance(user_id, proceeds)

        pnl = (price - holding["avg_price"]) * quantity
        pnl_pct = ((price / holding["avg_price"]) - 1) * 100 if holding["avg_price"] else 0
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        embed = discord.Embed(
            title="✅ 賣出成功",
            color=0xFF9100 if pnl >= 0 else 0xFF1744,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="交易對", value=f"`{symbol}`", inline=True)
        embed.add_field(name="成交價", value=f"`${price:,.4f}`", inline=True)
        embed.add_field(name="賣出數量", value=f"`{quantity:,.6f}`", inline=True)
        embed.add_field(name="入帳", value=f"`${proceeds:,.2f}` USDT", inline=True)
        embed.add_field(
            name=f"{pnl_emoji} 本次損益",
            value=f"`${pnl:+,.2f}` ({pnl_pct:+.2f}%)",
            inline=True,
        )
        embed.add_field(
            name="剩餘餘額",
            value=f"`${self.db.get_balance(user_id):,.2f}` USDT",
            inline=False,
        )
        embed.set_footer(text="Quant Sniper — 模擬交易")
        await ctx.send(embed=embed)

    # ── Command: /portfolio ──────────────────────────────────────────
    @commands.hybrid_command(name="portfolio", aliases=["p", "持倉"])
    async def portfolio(self, ctx: commands.Context) -> None:
        """查看你的模擬投資組合。"""
        user_id = str(ctx.author.id)
        self.db.ensure_user(user_id)

        balance = self.db.get_balance(user_id)
        holdings = self.db.get_all_holdings(user_id)

        embed = discord.Embed(
            title=f"💼 {ctx.author.display_name} 的投資組合",
            color=0x448AFF,
            timestamp=datetime.now(tz=timezone.utc),
        )

        total_value = balance  # start with cash

        if holdings:
            async with ctx.typing():
                lines = []
                for h in holdings:
                    try:
                        price = await self._get_price(h["symbol"])
                    except Exception:
                        price = h["avg_price"]  # fallback

                    market_val = h["quantity"] * price
                    cost_basis = h["quantity"] * h["avg_price"]
                    pnl = market_val - cost_basis
                    pnl_pct = ((price / h["avg_price"]) - 1) * 100 if h["avg_price"] else 0
                    total_value += market_val

                    emoji = "🟢" if pnl >= 0 else "🔴"
                    lines.append(
                        f"{emoji} **{h['symbol']}**\n"
                        f"   數量：`{h['quantity']:,.6f}` | 均價：`${h['avg_price']:,.4f}`\n"
                        f"   現價：`${price:,.4f}` | 市值：`${market_val:,.2f}`\n"
                        f"   損益：`${pnl:+,.2f}` ({pnl_pct:+.2f}%)"
                    )

                embed.add_field(
                    name="📦 持倉明細",
                    value="\n\n".join(lines) if lines else "（無持倉）",
                    inline=False,
                )
        else:
            embed.add_field(name="📦 持倉明細", value="（無持倉）", inline=False)

        roi = ((total_value / INITIAL_BALANCE) - 1) * 100
        roi_emoji = "📈" if roi >= 0 else "📉"

        embed.add_field(name="💵 現金餘額", value=f"`${balance:,.2f}` USDT", inline=True)
        embed.add_field(name="💎 總資產", value=f"`${total_value:,.2f}` USDT", inline=True)
        embed.add_field(name=f"{roi_emoji} 總 ROI", value=f"`{roi:+.2f}%`", inline=True)
        embed.set_footer(text="Quant Sniper — 模擬交易 | 初始資金 $10,000 USDT")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))
