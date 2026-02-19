
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from solcx import compile_standard, install_solc

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("deploy_opbnb")

# Load env
load_dotenv()

# Configuration
OPBNB_RPC_URL = "https://opbnb-testnet-rpc.bnbchain.org"
CHAIN_ID = 5611
SOLC_VERSION = "0.8.19"
CONTRACT_PATH = Path("contracts/Leaderboard.sol")

def deploy():
    # 1. Setup Web3
    logger.info(f"Connecting to opBNB Testnet: {OPBNB_RPC_URL}")
    w3 = Web3(Web3.HTTPProvider(OPBNB_RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        logger.error("Failed to connect to opBNB RPC.")
        return

    logger.info(f"Connected! Chain ID: {w3.eth.chain_id}")

    # 2. Setup Account
    private_key = os.getenv("BOT_WALLET_PRIVATE_KEY")
    if not private_key:
        logger.error("BOT_WALLET_PRIVATE_KEY not found in .env")
        return

    account = w3.eth.account.from_key(private_key)
    logger.info(f"Deployer Address: {account.address}")
    balance = w3.eth.get_balance(account.address)
    logger.info(f"Balance: {w3.from_wei(balance, 'ether')} tBNB")

    if balance == 0:
        logger.warning("⚠️ Wallet balance is 0! You need tBNB from opBNB Faucet.")
        logger.warning("Faucet: https://testnet.bnbchain.org/faucet-smart/opbnb")
        return

    # 3. Install & Compile Solidity
    logger.info(f"Installing solc v{SOLC_VERSION}...")
    install_solc(SOLC_VERSION)

    logger.info(f"Compiling {CONTRACT_PATH}...")
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        contract_source = f.read()

    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {"Leaderboard.sol": {"content": contract_source}},
            "settings": {
                "outputSelection": {
                    "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                }
            },
        },
        solc_version=SOLC_VERSION,
    )

    bytecode = compiled_sol["contracts"]["Leaderboard.sol"]["Leaderboard"]["evm"]["bytecode"]["object"]
    abi = compiled_sol["contracts"]["Leaderboard.sol"]["Leaderboard"]["abi"]

    # 4. Deploy
    logger.info("Deploying contract...")
    Leaderboard = w3.eth.contract(abi=abi, bytecode=bytecode)

    nonce = w3.eth.get_transaction_count(account.address)
    
    # Estimate Gas
    gas_estimate = Leaderboard.constructor().estimate_gas()
    
    # Build Transaction
    tx = Leaderboard.constructor().build_transaction({
        "chainId": CHAIN_ID,
        "gasPrice": w3.eth.gas_price,
        "from": account.address,
        "nonce": nonce,
        "gas": int(gas_estimate * 1.2) # Safety margin
    })

    # Sign & Send
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    logger.info(f"Transaction sent! Hash: {tx_hash.hex()}")
    logger.info("Waiting for receipt...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    logger.info("✅ Deployment Successful!")
    logger.info(f"Contract Address: {receipt.contractAddress}")
    logger.info("Please update your .env and README.md with this address.")

    # Optional: Save ABI to file
    with open("contracts/Leaderboard_ABI.json", "w") as f:
        json.dump(abi, f)
    logger.info("Saved ABI to contracts/Leaderboard_ABI.json")

if __name__ == "__main__":
    deploy()
