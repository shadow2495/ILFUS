// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title SecureFileShare
 * @dev Blockchain-based secure file sharing with access control, versioning,
 *      expiry, revocation, and audit trail
 */
contract SecureFileShare {

    

    struct FileRecord {
        bytes32   fileHash;         
        string    ipfsCid;           
        string    fileName;
        string    mimeType;
        uint256   fileSize;
        address   owner;
        uint256   uploadedAt;
        uint256   version;
        bool      isEncrypted;
        bool      isDeleted;
        string    encryptedKey;      
        string[]  tags;
    }

    struct AccessGrant {
        address   grantee;
        uint256   fileId;
        uint256   grantedAt;
        uint256   expiresAt;         
        bool      canReshare;
        bool      isRevoked;
        string    encryptedKey;      
        AccessLevel level;
    }

    struct AuditLog {
        address   actor;
        uint256   fileId;
        ActionType action;
        uint256   timestamp;
        string    metadata;
    }

    struct UserProfile {
        string    publicKey;        
        string    username;
        uint256   registeredAt;
        bool      isActive;
        uint256   totalFiles;
        uint256   totalShares;
    }

    // ENUMS 
    enum ActionType  { UPLOAD, SHARE, ACCESS, REVOKE, DELETE, VERSION_UPDATE }

    // STATE 

    uint256 private _fileIdCounter;
    uint256 private _grantIdCounter;
    uint256 private _logIdCounter;

    mapping(uint256 => FileRecord)   private _files;
    mapping(uint256 => AccessGrant)  private _grants;
    mapping(uint256 => AuditLog)     private _logs;
    mapping(address => UserProfile)  private _users;

    // owner  => list of file IDs
    mapping(address => uint256[])    private _ownerFiles;
    // fileId => list of grant IDs
    mapping(uint256 => uint256[])    private _fileGrants;
    // grantee => list of grant IDs
    mapping(address => uint256[])    private _userGrants;
    // fileHash => fileId (prevents duplicate uploads)
    mapping(bytes32 => uint256)      private _hashToFileId;
    // fileId => array of version fileIds (history)
    mapping(uint256 => uint256[])    private _fileVersions;

    // EVENTS 

    event FileUploaded(uint256 indexed fileId, address indexed owner, bytes32 fileHash, string ipfsCid);
    event FileShared(uint256 indexed fileId, address indexed owner, address indexed grantee, uint256 grantId, uint256 expiresAt);
    event AccessRevoked(uint256 indexed grantId, address indexed revokedBy, address indexed grantee);
    event FileAccessed(uint256 indexed fileId, address indexed accessor, uint256 timestamp);
    event FileDeleted(uint256 indexed fileId, address indexed owner);
    event FileVersioned(uint256 indexed oldFileId, uint256 indexed newFileId, address indexed owner);
    event UserRegistered(address indexed user, string username);

    // MODIFIERS 

    modifier onlyFileOwner(uint256 fileId) {
        require(_files[fileId].owner == msg.sender, "Not file owner");
        _;
    }

    modifier fileExists(uint256 fileId) {
        require(_files[fileId].owner != address(0), "File does not exist");
        require(!_files[fileId].isDeleted, "File has been deleted");
        _;
    }

    modifier userRegistered() {
        require(_users[msg.sender].isActive, "User not registered");
        _;
    }

    // USER MANAGEMENT 

    /**
     * @dev Register user with their public key for key exchange
     */
    function registerUser(string calldata username, string calldata publicKey) external {
        require(!_users[msg.sender].isActive, "Already registered");
        require(bytes(username).length > 0 && bytes(username).length <= 50, "Invalid username");
        require(bytes(publicKey).length > 0, "Public key required");

        _users[msg.sender] = UserProfile({
            publicKey:    publicKey,
            username:     username,
            registeredAt: block.timestamp,
            isActive:     true,
            totalFiles:   0,
            totalShares:  0
        });

        emit UserRegistered(msg.sender, username);
    }

    function updatePublicKey(string calldata newPublicKey) external userRegistered {
        _users[msg.sender].publicKey = newPublicKey;
    }

    function getUser(address user) external view returns (UserProfile memory) {
        return _users[user];
    }

    // FILE OPERATIONS 

    /**
     * @dev Upload a file record to the blockchain
     */
    function uploadFile(
        bytes32       fileHash,
        string calldata ipfsCid,
        string calldata fileName,
        string calldata mimeType,
        uint256       fileSize,
        bool          isEncrypted,
        string calldata encryptedKey,
        string[] calldata tags
    ) external userRegistered returns (uint256 fileId) {
        require(_hashToFileId[fileHash] == 0, "Duplicate file detected");
        require(bytes(ipfsCid).length > 0, "CID required");
        require(fileSize > 0, "Invalid file size");

        _fileIdCounter++;
        fileId = _fileIdCounter;

        _files[fileId] = FileRecord({
            fileHash:     fileHash,
            ipfsCid:      ipfsCid,
            fileName:     fileName,
            mimeType:     mimeType,
            fileSize:     fileSize,
            owner:        msg.sender,
            uploadedAt:   block.timestamp,
            version:      1,
            isEncrypted:  isEncrypted,
            isDeleted:    false,
            encryptedKey: encryptedKey,
            tags:         tags
        });

        _ownerFiles[msg.sender].push(fileId);
        _hashToFileId[fileHash] = fileId;
        _users[msg.sender].totalFiles++;

        _writeLog(msg.sender, fileId, ActionType.UPLOAD, "");

        emit FileUploaded(fileId, msg.sender, fileHash, ipfsCid);
    }

    /**
     * @dev Upload a new version of an existing file
     */
    function uploadVersion(
        uint256       originalFileId,
        bytes32       newFileHash,
        string calldata newIpfsCid,
        string calldata encryptedKey
    ) external userRegistered onlyFileOwner(originalFileId) fileExists(originalFileId) returns (uint256 newFileId) {
        FileRecord storage orig = _files[originalFileId];

        _fileIdCounter++;
        newFileId = _fileIdCounter;

        string[] memory tags = orig.tags;

        _files[newFileId] = FileRecord({
            fileHash:     newFileHash,
            ipfsCid:      newIpfsCid,
            fileName:     orig.fileName,
            mimeType:     orig.mimeType,
            fileSize:     orig.fileSize,
            owner:        msg.sender,
            uploadedAt:   block.timestamp,
            version:      orig.version + 1,
            isEncrypted:  orig.isEncrypted,
            isDeleted:    false,
            encryptedKey: encryptedKey,
            tags:         tags
        });

        _fileVersions[originalFileId].push(newFileId);
        _hashToFileId[newFileHash] = newFileId;
        _ownerFiles[msg.sender].push(newFileId);

        _writeLog(msg.sender, newFileId, ActionType.VERSION_UPDATE, "");
        emit FileVersioned(originalFileId, newFileId, msg.sender);
    }

    /**
     * @dev Soft-delete a file
     */
    function deleteFile(uint256 fileId) external onlyFileOwner(fileId) fileExists(fileId) {
        _files[fileId].isDeleted = true;
        _writeLog(msg.sender, fileId, ActionType.DELETE, "");
        emit FileDeleted(fileId, msg.sender);
    }

    function getFile(uint256 fileId) external view fileExists(fileId) returns (FileRecord memory) {
        require(
            _files[fileId].owner == msg.sender || _hasValidAccess(msg.sender, fileId),
            "Access denied"
        );
        return _files[fileId];
    }

    function getMyFiles() external view returns (uint256[] memory) {
        return _ownerFiles[msg.sender];
    }

    function getFileVersions(uint256 fileId) external view returns (uint256[] memory) {
        return _fileVersions[fileId];
    }

    // ACCESS CONTROL 

    /**
     * @dev Share a file with another user
     */
    function shareFile(
        uint256       fileId,
        address       grantee,
        uint256       expiresAt,
        bool          canReshare,
        string calldata encryptedKeyForGrantee,
        AccessLevel   level
    ) external userRegistered fileExists(fileId) returns (uint256 grantId) {
        FileRecord storage f = _files[fileId];
        require(
            f.owner == msg.sender ||
            (canReshare && _hasReshareAccess(msg.sender, fileId)),
            "No share permission"
        );
        require(grantee != msg.sender, "Cannot share with yourself");
        require(_users[grantee].isActive, "Grantee not registered");
        require(
            expiresAt == 0 || expiresAt > block.timestamp,
            "Expiry must be in future"
        );

        _grantIdCounter++;
        grantId = _grantIdCounter;

        _grants[grantId] = AccessGrant({
            grantee:      grantee,
            fileId:       fileId,
            grantedAt:    block.timestamp,
            expiresAt:    expiresAt,
            canReshare:   canReshare,
            isRevoked:    false,
            encryptedKey: encryptedKeyForGrantee,
            level:        level
        });

        _fileGrants[fileId].push(grantId);
        _userGrants[grantee].push(grantId);
        _users[msg.sender].totalShares++;

        _writeLog(msg.sender, fileId, ActionType.SHARE, "");
        emit FileShared(fileId, msg.sender, grantee, grantId, expiresAt);
    }

    /**
     * @dev Revoke a specific grant
     */
    function revokeAccess(uint256 grantId) external {
        AccessGrant storage g = _grants[grantId];
        require(
            _files[g.fileId].owner == msg.sender || g.grantee == msg.sender,
            "Not authorized to revoke"
        );
        require(!g.isRevoked, "Already revoked");

        g.isRevoked = true;
        _writeLog(msg.sender, g.fileId, ActionType.REVOKE, "");
        emit AccessRevoked(grantId, msg.sender, g.grantee);
    }

    /**
     * @dev Revoke ALL grants for a file (emergency revoke)
     */
    function revokeAllAccess(uint256 fileId) external onlyFileOwner(fileId) {
        uint256[] storage grantIds = _fileGrants[fileId];
        for (uint256 i = 0; i < grantIds.length; i++) {
            if (!_grants[grantIds[i]].isRevoked) {
                _grants[grantIds[i]].isRevoked = true;
                emit AccessRevoked(grantIds[i], msg.sender, _grants[grantIds[i]].grantee);
            }
        }
    }

    function getGrant(uint256 grantId) external view returns (AccessGrant memory) {
        return _grants[grantId];
    }

    function getMySharedFiles() external view returns (uint256[] memory) {
        return _userGrants[msg.sender];
    }

    function getFileGrants(uint256 fileId) external view onlyFileOwner(fileId) returns (uint256[] memory) {
        return _fileGrants[fileId];
    }

    // AUDIT & LOGS 

    function logAccess(uint256 fileId, string calldata metadata) external fileExists(fileId) {
        require(
            _files[fileId].owner == msg.sender || _hasValidAccess(msg.sender, fileId),
            "Access denied"
        );
        _writeLog(msg.sender, fileId, ActionType.ACCESS, metadata);
        emit FileAccessed(fileId, msg.sender, block.timestamp);
    }

    function getLog(uint256 logId) external view returns (AuditLog memory) {
        return _logs[logId];
    }

    function getTotalLogs() external view returns (uint256) {
        return _logIdCounter;
    }

    // INTERNAL HELPERS 

    function _hasValidAccess(address user, uint256 fileId) internal view returns (bool) {
        uint256[] storage grantIds = _userGrants[user];
        for (uint256 i = 0; i < grantIds.length; i++) {
            AccessGrant storage g = _grants[grantIds[i]];
            if (
                g.fileId == fileId &&
                !g.isRevoked &&
                (g.expiresAt == 0 || g.expiresAt > block.timestamp)
            ) {
                return true;
            }
        }
        return false;
    }

    function _hasReshareAccess(address user, uint256 fileId) internal view returns (bool) {
        uint256[] storage grantIds = _userGrants[user];
        for (uint256 i = 0; i < grantIds.length; i++) {
            AccessGrant storage g = _grants[grantIds[i]];
            if (
                g.fileId == fileId &&
                g.canReshare &&
                !g.isRevoked &&
                (g.expiresAt == 0 || g.expiresAt > block.timestamp)
            ) {
                return true;
            }
        }
        return false;
    }

    function _writeLog(address actor, uint256 fileId, ActionType action, string memory metadata) internal {
        _logIdCounter++;
        _logs[_logIdCounter] = AuditLog({
            actor:     actor,
            fileId:    fileId,
            action:    action,
            timestamp: block.timestamp,
            metadata:  metadata
        });
    }

    // VIEW HELPERS

    function checkDuplicate(bytes32 fileHash) external view returns (bool exists, uint256 fileId) {
        fileId = _hashToFileId[fileHash];
        exists = fileId != 0;
    }

    function totalFiles() external view returns (uint256) { return _fileIdCounter; }
    function totalGrants() external view returns (uint256) { return _grantIdCounter; }
}
