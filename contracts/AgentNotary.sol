// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgentNotary
 * @dev Avalanche Fuji Testnet üzerinde Nexa-Trader otonom ajanın aldığı işlem kararlarını
 * ve hash kanıtlarını değiştirilemez (immutable) şekilde zincir üzerine mühürleyen akıllı sözleşme.
 */
contract AgentNotary {
    event DecisionNotarized(
        bytes32 indexed decisionHash,
        string action,
        string instId,
        uint256 notionalUsdt,
        uint256 timestamp,
        address indexed notary
    );

    struct NotaryRecord {
        bytes32 decisionHash;
        string action;
        string instId;
        uint256 notionalUsdt;
        uint256 timestamp;
        address notary;
    }

    NotaryRecord[] public records;
    mapping(bytes32 => bool) public isNotarized;

    /**
     * @notice Otonom ajanın aldığı işlem kararını Avalanche blokzincirine kaydeder.
     * @param decisionHash Kararın SHA256 / Keccak256 özet hash'i
     * @param action Yapılan işlem (BUY, SELL vb.)
     * @param instId İşlem yapılan parite (Örn: AVAX-USDT)
     * @param notionalUsdt İşlem büyüklüğü (Sent cinsinden veya tam sayı)
     */
    function notarizeDecision(
        bytes32 decisionHash,
        string calldata action,
        string calldata instId,
        uint256 notionalUsdt
    ) external returns (uint256 recordId) {
        require(!isNotarized[decisionHash], "Karar zaten noter onayli");

        records.push(NotaryRecord({
            decisionHash: decisionHash,
            action: action,
            instId: instId,
            notionalUsdt: notionalUsdt,
            timestamp: block.timestamp,
            notary: msg.sender
        }));

        isNotarized[decisionHash] = true;
        recordId = records.length - 1;

        emit DecisionNotarized(decisionHash, action, instId, notionalUsdt, block.timestamp, msg.sender);
    }

    function totalRecords() external view returns (uint256) {
        return records.length;
    }
}
