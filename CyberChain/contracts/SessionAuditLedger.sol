// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SessionAuditLedger
 * @notice Authoritative on-chain forensic audit ledger recording user session lifecycles
 *         and SQL modifications upon logout.
 */
contract SessionAuditLedger {
    struct SessionLog {
        string userId;
        string username;
        string sessionId;
        uint256 entryTime;
        uint256 exitTime;
        uint256 sqlModificationsCount;
        string sqlModificationsHash;
        string detailsJson;
        uint256 blockTimestamp;
        address recordedBy;
    }

    // Mapping from sessionId to SessionLog
    mapping(string => SessionLog) private sessions;

    // Array of all session IDs in insertion order
    string[] private sessionIds;

    // Mapping from userId to array of session IDs
    mapping(string => string[]) private userSessionMap;

    event SessionLogoutRecorded(
        string indexed userId,
        string indexed sessionId,
        uint256 entryTime,
        uint256 exitTime,
        uint256 sqlModificationsCount,
        string sqlModificationsHash,
        address indexed recordedBy
    );

    /**
     * @notice Records a completed user session upon logout.
     * @param userId The unique user ID of the logged out user.
     * @param username The username of the logged out user.
     * @param sessionId The authoritative session ID or JTI.
     * @param entryTime UNIX timestamp of session creation (login).
     * @param exitTime UNIX timestamp of session termination (logout).
     * @param sqlModificationsCount Count of SQL modifications performed during the session.
     * @param sqlModificationsHash SHA-256 hash digest of all SQL modifications.
     * @param detailsJson Serialized JSON containing details of the modifications.
     */
    function recordSessionLogout(
        string calldata userId,
        string calldata username,
        string calldata sessionId,
        uint256 entryTime,
        uint256 exitTime,
        uint256 sqlModificationsCount,
        string calldata sqlModificationsHash,
        string calldata detailsJson
    ) external returns (bool) {
        require(bytes(sessionId).length > 0, "SessionAuditLedger: sessionId cannot be empty");
        require(sessions[sessionId].entryTime == 0, "SessionAuditLedger: session already recorded");

        sessions[sessionId] = SessionLog({
            userId: userId,
            username: username,
            sessionId: sessionId,
            entryTime: entryTime,
            exitTime: exitTime,
            sqlModificationsCount: sqlModificationsCount,
            sqlModificationsHash: sqlModificationsHash,
            detailsJson: detailsJson,
            blockTimestamp: block.timestamp,
            recordedBy: msg.sender
        });

        sessionIds.push(sessionId);
        userSessionMap[userId].push(sessionId);

        emit SessionLogoutRecorded(
            userId,
            sessionId,
            entryTime,
            exitTime,
            sqlModificationsCount,
            sqlModificationsHash,
            msg.sender
        );

        return true;
    }

    /**
     * @notice Retrieves full audit record for a session.
     */
    function getSession(string calldata sessionId) external view returns (SessionLog memory) {
        SessionLog memory s = sessions[sessionId];
        require(s.entryTime > 0, "SessionAuditLedger: session not found");
        return s;
    }

    /**
     * @notice Retrieves all session IDs recorded for a given user.
     */
    function getUserSessions(string calldata userId) external view returns (string[] memory) {
        return userSessionMap[userId];
    }

    /**
     * @notice Returns total number of recorded sessions.
     */
    function totalSessions() external view returns (uint256) {
        return sessionIds.length;
    }

    /**
     * @notice Checks if a session has already been anchored.
     */
    function isSessionRecorded(string calldata sessionId) external view returns (bool) {
        return sessions[sessionId].entryTime > 0;
    }
}
