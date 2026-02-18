// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Leaderboard
 * @notice 量化狙擊手 — 鏈上模擬交易排行榜
 * @dev 儲存使用者的 ROI 分數，支援查詢前 N 名排名
 */
contract Leaderboard {
    struct Player {
        address wallet;
        string discordId;
        int256 roiBps; // ROI in basis points (e.g. 1234 = 12.34%)
        uint256 timestamp;
    }

    address public owner;
    Player[] public players;
    mapping(string => uint256) private _discordIndex; // discordId => index+1 (0 means not found)

    event ScoreSubmitted(string indexed discordId, address wallet, int256 roiBps, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice 提交或更新玩家的 ROI 分數
     * @param discordId Discord 使用者 ID
     * @param roiBps ROI（基點），例如 1234 = 12.34%
     */
    function submitScore(string calldata discordId, int256 roiBps) external onlyOwner {
        uint256 idx = _discordIndex[discordId];

        if (idx == 0) {
            // 新玩家
            players.push(Player({
                wallet: tx.origin,
                discordId: discordId,
                roiBps: roiBps,
                timestamp: block.timestamp
            }));
            _discordIndex[discordId] = players.length; // store index+1
        } else {
            // 更新現有玩家
            Player storage p = players[idx - 1];
            p.roiBps = roiBps;
            p.timestamp = block.timestamp;
        }

        emit ScoreSubmitted(discordId, tx.origin, roiBps, block.timestamp);
    }

    /**
     * @notice 取得排行榜上的玩家數量
     */
    function getPlayerCount() external view returns (uint256) {
        return players.length;
    }

    /**
     * @notice 取得指定索引的玩家資訊
     */
    function getPlayer(uint256 index) external view returns (
        address wallet,
        string memory discordId,
        int256 roiBps,
        uint256 timestamp
    ) {
        require(index < players.length, "Index out of bounds");
        Player storage p = players[index];
        return (p.wallet, p.discordId, p.roiBps, p.timestamp);
    }

    /**
     * @notice 取得前 N 名玩家（按 ROI 降序，鏈下排序參考用）
     * @dev 為節省 Gas，此函式回傳所有玩家，由鏈下排序
     */
    function getAllPlayers() external view returns (Player[] memory) {
        return players;
    }

    /**
     * @notice 查詢特定 Discord 使用者的分數
     */
    function getScoreByDiscordId(string calldata discordId) external view returns (int256 roiBps, uint256 timestamp) {
        uint256 idx = _discordIndex[discordId];
        require(idx > 0, "Player not found");
        Player storage p = players[idx - 1];
        return (p.roiBps, p.timestamp);
    }
}
