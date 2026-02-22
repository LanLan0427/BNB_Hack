"""
Paper Degen — AI Trading Assistant Discord Bot
Entry point: loads environment, initialises the bot, and registers cogs.
"""

import asyncio
import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("quant_sniper")

# ── Environment ──────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

if not DISCORD_TOKEN:
    raise EnvironmentError("DISCORD_TOKEN is not set in .env")

# ── Bot setup ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=commands.DefaultHelpCommand(no_category="General"),
)

# ── Cog loader ───────────────────────────────────────────────────────
COGS = [
    "cogs.market",
    "cogs.game",
    "cogs.chain",
    "cogs.alert",
]


async def load_cogs() -> None:
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info("Loaded cog: %s", cog)
        except Exception as exc:
            logger.error("Failed to load cog %s: %s", cog, exc)


# ── Events ───────────────────────────────────────────────────────────
@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    logger.info("Connected to %d guild(s)", len(bot.guilds))

    # Sync slash commands to Discord
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash command(s)", len(synced))
    except Exception as exc:
        logger.error("Failed to sync slash commands: %s", exc)

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="/analyze | /chart | /alert",
        )
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ 缺少參數：`{error.param.name}`。請使用 `{COMMAND_PREFIX}help` 查看用法。")
        return
    logger.error("Unhandled command error: %s", error)
    await ctx.send("❌ 發生未預期的錯誤，請稍後再試。")


# ── Main ─────────────────────────────────────────────────────────────
async def main() -> None:
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
