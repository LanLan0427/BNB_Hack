import requests
import os
from dotenv import load_dotenv

load_dotenv()

# We need the source code as string
with open("contracts/Leaderboard.sol", "r", encoding="utf-8") as f:
    source_code = f.read()

API_KEY = os.getenv("OPBNBSCAN_API_KEY", "YOUR_API_KEY") 
CONTRACT_ADDRESS = "0x52708366F7A11c166Bb94d398951719F032CB945"

# opBNB Testnet Explorer API Endpoint
API_URL = "https://open-platform.nodereal.io/b4a47d665a834d18b6c267359b1ae848/op-bnb-testnet/contract/"

data = {
    "module": "contract",
    "action": "verifysourcecode",
    "apikey": API_KEY,
    "contractaddress": CONTRACT_ADDRESS,
    "sourceCode": source_code,
    "codeformat": "0", # 0 for Single File
    "contractname": "Leaderboard",
    "compilerversion": "v0.8.19+commit.7dd6d404", # Needs to match the deployed compiler
    "optimizationUsed": "0", # 0 for No, 1 for Yes
    "runs": "200",
    "evmversion": "paris",
    "licenseType": "3" # 3 is for MIT
}

response = requests.post(API_URL, data=data)

print(response.json())
