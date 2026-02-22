import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# Setup Web3 Provider
RPC_URL = os.getenv("OPBNB_RPC_URL", "https://opbnb-testnet-rpc.bnbchain.org")
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract Info
CONTRACT_ADDRESS = os.getenv("OPBNB_CONTRACT_ADDRESS", "0x52708366F7A11c166Bb94d398951719F032CB945")
PRIVATE_KEY = os.getenv("BOT_WALLET_PRIVATE_KEY")

if not PRIVATE_KEY:
    raise ValueError("Private key missing.")

account = web3.eth.account.from_key(PRIVATE_KEY)

# ABI (Only what we need)
ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "discordId", "type": "string"},
            {"internalType": "int256", "name": "roiBps", "type": "int256"}
        ],
        "name": "submitScore",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

contract = web3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

def send_tx(discord_id, roi):
    nonce = web3.eth.get_transaction_count(account.address)
    
    # Needs a higher gas limit slightly for submitting new strings
    tx = contract.functions.submitScore(discord_id, roi).build_transaction({
        'chainId': 5611, # opBNB testnet chain id
        'gas': 300000,
        'gasPrice': web3.eth.gas_price,
        'nonce': nonce,
    })

    signed_tx = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transaction sent: {web3.to_hex(tx_hash)}")
    
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Transaction mined in block {receipt.blockNumber}")

# Send 2 transactions
try:
    print("Sending transaction 1...")
    send_tx("USER_HACKATHON_JUDGE_1", 1500) # 15% ROI
    
    print("\nSending transaction 2...")
    send_tx("USER_HACKATHON_JUDGE_2", -500) # -5% ROI
except Exception as e:
    print(f"Error: {e}")
