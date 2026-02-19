"""
BNB Chain Cog — !leaderboard, !submit
鏈上排行榜功能，透過 Web3.py 與 BSC Testnet 上的 Leaderboard 合約互動。
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger("quant_sniper.chain")

# ── 合約 ABI（僅包含需要的函式） ─────────────────────────────────
LEADERBOARD_ABI = json.loads("""
[
    {
        "inputs": [{"internalType": "string", "name": "discordId", "type": "string"}, {"internalType": "int256", "name": "roiBps", "type": "int256"}],
        "name": "submitScore",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getAllPlayers",
        "outputs": [{"components": [{"internalType": "address", "name": "wallet", "type": "address"}, {"internalType": "string", "name": "discordId", "type": "string"}, {"internalType": "int256", "name": "roiBps", "type": "int256"}, {"internalType": "uint256", "name": "timestamp", "type": "uint256"}], "internalType": "struct Leaderboard.Player[]", "name": "", "type": "tuple[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getPlayerCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "discordId", "type": "string"}],
        "name": "getScoreByDiscordId",
        "outputs": [{"internalType": "int256", "name": "roiBps", "type": "int256"}, {"internalType": "uint256", "name": "timestamp", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]
""")

INITIAL_BALANCE = 10_000.0


class Chain(commands.Cog, name="⛓️ 鏈上功能"):
    """BNB Chain 鏈上排行榜。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Web3 setup - 優先使用 opBNB
        opbnb_rpc = os.getenv("OPBNB_RPC_URL")
        bsc_rpc = os.getenv("BSC_RPC_URL", "https://data-seed-prebsc-1-s1.bnbchain.org:8545")
        
        if opbnb_rpc:
            self.network_name = "opBNB Testnet"
            rpc_url = opbnb_rpc
            contract_addr = os.getenv("OPBNB_CONTRACT_ADDRESS", os.getenv("LEADERBOARD_CONTRACT_ADDRESS", ""))
        else:
            self.network_name = "BSC Testnet"
            rpc_url = bsc_rpc
            contract_addr = os.getenv("LEADERBOARD_CONTRACT_ADDRESS", "")

        logger.info(f"Connecting to {self.network_name}...")
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            logger.warning("無法連線到 RPC: %s", rpc_url)

        # 合約
        if contract_addr:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_addr),
                abi=LEADERBOARD_ABI,
            )
            logger.info(f"Loaded Leaderboard contract at {contract_addr}")
        else:
            self.contract = None
            logger.warning("CONTRACT_ADDRESS 未設定，鏈上功能將無法使用")

        # Bot 錢包（用於發送交易）
        self.private_key = os.getenv("BOT_WALLET_PRIVATE_KEY", "")
        if self.private_key:
            self.bot_account = self.w3.eth.account.from_key(self.private_key)
        else:
            self.bot_account = None
            logger.warning("BOT_WALLET_PRIVATE_KEY 未設定，無法提交鏈上交易")

    def _get_game_cog(self):
        """取得 Game cog 以讀取使用者資料。"""
        return self.bot.get_cog("🎮 模擬交易")

    def _calculate_roi_bps(self, user_id: str) -> int | None:
        """計算使用者的 ROI（基點）。"""
        game = self._get_game_cog()
        if not game:
            return None

        game.db.ensure_user(user_id)
        balance = game.db.get_balance(user_id)
        holdings = game.db.get_all_holdings(user_id)

        total_value = balance
        for h in holdings:
            # 用均價估算（鏈上提交不需要即時價格的精確度）
            total_value += h["quantity"] * h["avg_price"]

        roi = ((total_value / INITIAL_BALANCE) - 1) * 100
        return int(roi * 100)  # 轉為基點

    # ── Command: /submit ─────────────────────────────────────────────
    @commands.hybrid_command(name="submit", aliases=["提交"])
    async def submit(self, ctx: commands.Context) -> None:
        """將你的模擬交易 ROI 提交到 BNB Chain 排行榜。"""
        if not self.contract or not self.bot_account:
            await ctx.send("❌ 鏈上功能尚未設定，請聯繫管理員。")
            return

        user_id = str(ctx.author.id)
        roi_bps = self._calculate_roi_bps(user_id)

        if roi_bps is None:
            await ctx.send("❌ 無法計算你的 ROI，請先用 `!portfolio` 確認帳號。")
            return

        async with ctx.typing():
            try:
                # 建構交易
                nonce = self.w3.eth.get_transaction_count(self.bot_account.address)
                tx = self.contract.functions.submitScore(
                    user_id, roi_bps
                ).build_transaction({
                    "from": self.bot_account.address,
                    "nonce": nonce,
                    "gas": 200_000,
                    "gasPrice": self.w3.eth.gas_price,
                    "chainId": self.w3.eth.chain_id,
                })

                # 簽名並發送
                signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

                roi_pct = roi_bps / 100

                if receipt["status"] == 1:
                    if "opBNB" in self.network_name:
                        explorer_url = f"https://opbnb-testnet.bscscan.com/tx/{tx_hash.hex()}"
                        footer_text = "Quant Sniper — opBNB Testnet (Layer 2)"
                    else:
                        explorer_url = f"https://testnet.bscscan.com/tx/{tx_hash.hex()}"
                        footer_text = "Quant Sniper — BSC Testnet"

                    embed = discord.Embed(
                        title="⛓️ 鏈上提交成功！",
                        color=0x00E676,
                        timestamp=datetime.now(tz=timezone.utc),
                    )
                    embed.add_field(name="📊 你的 ROI", value=f"`{roi_pct:+.2f}%`", inline=True)
                    embed.add_field(
                        name="🔗 交易 Hash",
                        value=f"[View on Explorer]({explorer_url})",
                        inline=True,
                    )
                    embed.set_footer(text=footer_text)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ 鏈上交易失敗，請稍後再試。")

            except Exception as exc:
                logger.error("鏈上提交失敗: %s", exc)
                await ctx.send(f"❌ 鏈上提交失敗：`{exc}`")

    # ── Command: /leaderboard ────────────────────────────────────────
    @commands.hybrid_command(name="leaderboard", aliases=["lb", "排行榜"])
    async def leaderboard(self, ctx: commands.Context) -> None:
        """顯示鏈上模擬交易排行榜。"""
        if not self.contract:
            await ctx.send("❌ 鏈上功能尚未設定，請聯繫管理員。")
            return

        async with ctx.typing():
            try:
                players = self.contract.functions.getAllPlayers().call()
            except Exception as exc:
                logger.error("讀取排行榜失敗: %s", exc)
                await ctx.send("❌ 無法讀取鏈上排行榜。")
                return

            if not players:
                await ctx.send("📭 排行榜目前沒有玩家，快用 `!submit` 成為第一位！")
                return

            # 按 ROI 降序排列
            sorted_players = sorted(players, key=lambda p: p[2], reverse=True)

            embed = discord.Embed(
                title="🏆 鏈上模擬交易排行榜",
                description="資料來源：BNB Chain (BSC Testnet)",
                color=0xF0B90B,  # BNB 黃
                timestamp=datetime.now(tz=timezone.utc),
            )

            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, player in enumerate(sorted_players[:10]):
                _wallet, discord_id, roi_bps, _ts = player
                roi_pct = roi_bps / 100
                medal = medals[i] if i < 3 else f"`#{i+1}`"

                # 嘗試取得 Discord 使用者名稱
                try:
                    user = await self.bot.fetch_user(int(discord_id))
                    name = user.display_name
                except Exception:
                    name = f"User#{discord_id[-4:]}"

                emoji = "📈" if roi_bps >= 0 else "📉"
                lines.append(f"{medal} **{name}** — {emoji} `{roi_pct:+.2f}%`")

            embed.add_field(name="排名", value="\n".join(lines), inline=False)
            embed.set_footer(text="Quant Sniper — 用 !submit 提交你的成績")

            await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Chain(bot))
