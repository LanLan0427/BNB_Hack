require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

module.exports = {
  solidity: "0.8.19",
  networks: {
    opbnbTestnet: {
      url: "https://opbnb-testnet-rpc.bnbchain.org",
      accounts: [process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000000"],
    },
  },
  etherscan: {
    apiKey: {
      opbnbTestnet: "YOUR_BSCSCAN_API_KEY",
    },
    customChains: [
      {
        network: "opbnbTestnet",
        chainId: 5611,
        urls: {
          apiURL: "https://api-opbnb-testnet.bscscan.com/api",
          browserURL: "https://testnet.opbnbscan.com/",
        },
      },
    ],
  },
};
