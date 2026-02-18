# 🎯 Quant Sniper — AI 量化狙擊手

<div align="center">

**BNB Chain 上的 AI 交易助手 Discord Bot**

讓不懂加密貨幣的人也能輕鬆體驗交易的樂趣 🚀

[![BNB Chain](https://img.shields.io/badge/BNB_Chain-BSC_Testnet-F0B90B?style=for-the-badge&logo=binance)](https://www.bnbchain.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![Discord](https://img.shields.io/badge/Discord_Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Gemini](https://img.shields.io/badge/Gemini_AI-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)

</div>

---

## 📖 專案簡介

**Quant Sniper（量化狙擊手）** 是一個為 **BNB Hack: Online Edition** 打造的 Discord Bot，旨在降低加密貨幣交易的門檻。透過 AI 驅動的市場分析和模擬交易遊戲，讓任何人都能零風險地體驗交易世界。

### 🌟 核心特色

| 功能 | 說明 |
|---|---|
| 🤖 **AI 市場分析** | Gemini AI 扮演毒舌華爾街交易員，用繁體中文給出犀利評論 |
| 🎮 **模擬交易遊戲** | 每人 10,000 USDT 虛擬資金，以即時價格買賣 |
| ⛓️ **鏈上排行榜** | ROI 成績上鏈到 BNB Chain（BSC Testnet），公開透明 |
| 📊 **即時報價** | 串接 Binance API，取得最新市場數據 |

---

## 🏗️ 系統架構

```mermaid
graph TB
    subgraph Discord
        U[使用者] -->|指令| Bot[Quant Sniper Bot]
    end

    subgraph Cogs
        Bot --> M[market.py<br/>市場分析]
        Bot --> G[game.py<br/>模擬交易]
        Bot --> C[chain.py<br/>鏈上功能]
    end

    subgraph 外部服務
        M -->|OHLCV 數據| Binance[Binance API<br/>ccxt]
        M -->|AI 分析| Gemini[Gemini AI]
        G -->|即時報價| Binance
        G -->|持倉數據| SQLite[(SQLite DB)]
        C -->|讀寫合約| BSC[BSC Testnet<br/>Web3.py]
    end

    BSC --> SC[Leaderboard.sol<br/>智能合約]
```

---

## 🚀 快速開始

### 前置需求
- Python 3.10+
- [Discord Bot Token](https://discord.com/developers/applications)
- [Gemini API Key](https://aistudio.google.com/app/apikey)
- (可選) BSC Testnet 錢包 & [tBNB](https://www.bnbchain.org/en/testnet-faucet)

### 安裝步驟

```bash
# 1. Clone 專案
git clone https://github.com/LanLan0427/BNB_Hack.git
cd BNB_Hack

# 2. 建立虛擬環境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. 安裝相依套件
pip install -r requirements.txt

# 4. 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的 API Keys

# 5. 啟動 Bot
python main.py
```

---

## 📋 指令一覽

| 指令 | 別名 | 說明 |
|---|---|---|
| `!analyze [symbol]` | `!a`, `!分析` | AI 分析市場走勢（預設 BNB/USDT） |
| `!buy [symbol] [金額]` | `!買` | 買入代幣（花費 USDT） |
| `!sell [symbol] [數量]` | `!賣` | 賣出代幣 |
| `!portfolio` | `!p`, `!持倉` | 查看投資組合與 ROI |
| `!submit` | `!提交` | 將 ROI 提交到鏈上排行榜 |
| `!leaderboard` | `!lb`, `!排行榜` | 查看鏈上排行榜 |

---

## 📁 專案結構

```
quant-sniper/
├── main.py                     # Bot 入口
├── cogs/
│   ├── market.py               # AI 市場分析（ccxt + Gemini）
│   ├── game.py                 # 模擬交易（SQLite）
│   └── chain.py                # 鏈上排行榜（Web3.py）
├── contracts/
│   └── Leaderboard.sol         # 排行榜智能合約
├── data/                       # SQLite 資料庫（自動建立）
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⛓️ 智能合約

**Leaderboard.sol** 部署於 BSC Testnet：

- **合約地址**：`TBD`
- **BscScan**：[查看合約](https://testnet.bscscan.com/address/TBD)
- **功能**：儲存玩家 ROI 分數、查詢排名

---

## 🛠️ 技術棧

| 技術 | 用途 |
|---|---|
| `discord.py` | Discord Bot 框架 |
| `ccxt` | Binance 市場數據 API |
| `google-generativeai` | Gemini AI 市場分析 |
| `web3.py` | BNB Chain 智能合約互動 |
| `sqlite3` | 本地模擬交易資料儲存 |
| `Solidity` | 鏈上排行榜智能合約 |

---

## 📄 License

MIT License — 詳見 [LICENSE](LICENSE) 文件

---

<div align="center">

**Built with ❤️ for BNB Hack: Online Edition**

</div>
