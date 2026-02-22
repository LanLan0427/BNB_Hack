import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPBNBSCAN_API_KEY", "YOUR_API_KEY") 
# NodeReal opBNB Testnet Explorer API Endpoint
API_URL = "https://open-platform.nodereal.io/b4a47d665a834d18b6c267359b1ae848/op-bnb-testnet/contract/"

# The GUID from the previous verification submission response
guid = "1694138c5a617f21f5a25ac55bbaa873" 

params = {
    "module": "contract",
    "action": "checkverifystatus",
    "apikey": API_KEY,
    "guid": guid
}

print("Checking verification status...")
for _ in range(5):
    response = requests.get(API_URL, params=params)
    result = response.json()
    print(result)
    
    if result.get('result') in ["Pending in queue", "Unknown UID"]:
        time.sleep(3)
    else:
        break
