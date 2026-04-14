# ILFUS
Immutable ledger file upload system



**End-to-end encrypted file storage with blockchain verification, IPFS pinning, and granular access control.**
## 🌟 What Is This Project?

**SecureFileShare** is a decentralized file storage and sharing platform that combines:

- **Blockchain Technology** — Every file upload, share, and access event is recorded as an immutable transaction, ensuring a tamper-proof audit trail.
- **IPFS (InterPlanetary File System)** — Files are addressed by their content hash (CID), enabling decentralized, distributed storage.
- **End-to-End Encryption** — Files are encrypted with AES-256-GCM before storage, and encryption keys are exchanged via RSA key pairs.
- **Granular Access Control** — File owners can share files with specific users, set access levels (VIEW/DOWNLOAD/RESHARE), set expiry times, and revoke access at any time.

Think of it as **Google Drive meets Blockchain** — you get the convenience of cloud storage with the security and transparency of a decentralized ledger.

---

## 🔄 How Does It Work?

### The Big Picture

```
┌─────────────────┐     REST API      ┌──────────────────┐
│                  │  ◄──────────────► │                  │
│   Streamlit      │                   │   FastAPI         │
│   Frontend       │                   │   Backend         │
│   (Port 8501)    │                   │   (Port 8000)     │
│                  │                   │                   │
└─────────────────┘                   └────────┬──────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                              ▼                ▼                ▼
                     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                     │  PostgreSQL  │  │  File System  │  │  Blockchain  │
                     │  Database    │  │  (uploads/)   │  │  (Ethereum)  │
                     │              │  │              │  │              │
                     │  Users       │  │  Encrypted   │  │  Tx Hashes   │
                     │  Files       │  │  File Data   │  │  File Hashes │
                     │  Grants      │  │              │  │  Audit Trail │
                     │  Audit Logs  │  │              │  │              │
                     └──────────────┘  └──────────────┘  └──────────────┘
```

### Step-by-Step: What Happens When You Upload a File

```
1. USER selects a file in the Streamlit UI
           │
           ▼
2. Frontend sends the file to FastAPI backend
   POST /files/upload (multipart/form-data)
           │
           ▼
3. Backend ENCRYPTS the file (AES-256-GCM)
   - Generates a unique encryption key
   - Encrypts the file content
           │
           ▼
4. Backend computes SHA-256 HASH of the file
   - This hash uniquely identifies the file content
   - Any change to the file = different hash
           │
           ▼
5. Backend PINS the file to IPFS
   - Gets back a Content Identifier (CID)
   - CID = content-addressed storage (e.g., QmX7b5f...)
           │
           ▼
6. Backend records the hash on the BLOCKCHAIN
   - Calls the Solidity smart contract
   - Creates an immutable, verifiable record
   - Returns a transaction hash (e.g., 0xabc...)
           │
           ▼
7. Backend saves METADATA to PostgreSQL
   - File name, size, MIME type, owner
   - IPFS CID, SHA-256 hash, tx hash
   - Tags, description, encryption info
           │
           ▼
8. Backend saves ENCRYPTED FILE to disk (uploads/)
           │
           ▼
9. Frontend shows SUCCESS with all verification details
   - IPFS CID, file hash, blockchain tx hash
```

### Step-by-Step: What Happens When You Share a File

```
1. Owner selects FILE + RECIPIENT wallet address
           │
           ▼
2. Owner chooses ACCESS LEVEL:
   - VIEW    = can see file metadata only
   - DOWNLOAD = can download the file
   - RESHARE  = can re-share with others
           │
           ▼
3. Owner sets EXPIRY (optional):
   - 1 hour, 24 hours, 7 days, 30 days, or never
           │
           ▼
4. Backend creates an ACCESS GRANT:
   - Records in database (grants table)
   - Records on blockchain (smart contract)
   - Encrypts the file key with recipient's public key
           │
           ▼
5. Recipient gets a NOTIFICATION
   - "Alice shared 'report.pdf' with you (DOWNLOAD access)"
           │
           ▼
6. Recipient can now access the file
   - Based on their granted access level
   - Until the expiry time (if set)
   - Unless the owner REVOKES access
```

### Step-by-Step: How File Integrity Verification Works

```
1. User selects a file to verify
           │
           ▼
2. Backend reads the STORED HASH from database
   (the hash computed at upload time)
           │
           ▼
3. Backend reads the actual file from disk
   and RECOMPUTES the SHA-256 hash
           │
           ▼
4. Backend COMPARES the two hashes:
   - MATCH    ✅ = file has NOT been tampered with
   - MISMATCH ❌ = file has been modified/corrupted
           │
           ▼
5. Backend also checks BLOCKCHAIN CONFIRMATION
   - Was the file hash recorded on-chain? ✅/❌
```

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit | Python-based web UI with custom CSS |
| **Backend** | FastAPI | High-performance REST API |
| **Database** | PostgreSQL / SQLite | User data, file metadata, access grants |
| **Blockchain** | Solidity (Ethereum) | Immutable audit trail, access control |
| **Storage** | IPFS + Local disk | Decentralized content-addressed storage |
| **Charts** | Plotly | Interactive analytics visualizations |
| **Auth** | JWT + bcrypt | Token-based authentication |
| **Encryption** | AES-256-GCM + RSA | File encryption + key exchange |

---

## 📁 Project Structure

```
suro/
├── frontend/
│   └── app.py              ← Streamlit UI (11 pages, 600+ lines)
│
├── backend/
│   ├── server.py            ← FastAPI server (25+ endpoints, 1000+ lines)
│   ├── uploads/             ← Encrypted file storage
│   └── secureshare.db       ← SQLite database (auto-created)
│
├── contracts/
│   ├── FileShare.sol        ← Solidity smart contract (411 lines)
│   └── SecureFileShare_Report.docx
│
├── Database/
│   └── schema.sql           ← PostgreSQL schema (production-ready)
│
├── requirements.txt         ← Python dependencies
├── .env                     ← Environment variables
├── run.bat                  ← One-click launcher (Windows)
└── README.md                ← This file
```

---

## ✨ Features

### 🔐 Authentication & Identity
- **Wallet-based login** — Users register with an Ethereum wallet address
- **Password protection** — bcrypt-hashed passwords
- **JWT tokens** — Secure, stateless session management
- **RSA key pairs** — Auto-generated for each user for encryption key exchange

### 📁 File Management
- **Upload** with drag-and-drop UI
- **Search** files by name, tags, or description
- **Filter** by file type (Images, Videos, Documents, Archives, PDFs)
- **Sort** by date, name, or size
- **Download** files with audit logging
- **Bulk delete** multiple files at once
- **File versioning** support in the smart contract
- **Duplicate detection** via SHA-256 hash comparison

### 🔒 Encryption & Security
- **AES-256-GCM** encryption for files at rest
- **RSA key exchange** for sharing encrypted files
- **SHA-256 hashing** for file integrity verification
- **File integrity checker** — recompute hash and compare

### 🔗 Sharing & Access Control
- **Granular access levels**: VIEW, DOWNLOAD, RESHARE
- **Time-based expiry**: 1 hour to 30 days, or never
- **Revocable access** — instantly revoke any share
- **Reshare control** — allow/disallow recipients from re-sharing
- **Notification system** — recipients get notified of new shares

### ⛓ Blockchain Integration
- **On-chain audit trail** — every action recorded as a transaction
- **Transaction explorer** — browse your blockchain transactions
- **Transaction verification** — verify any tx hash
- **Smart contract** — Solidity contract with full access control logic
- **Network status** — real-time blockchain connection info

### 📊 Analytics & Monitoring
- **Dashboard** with 4 key metric cards
- **Storage breakdown** pie chart by file type
- **File count distribution** chart
- **Activity timeline** — recent actions with timestamps
- **System-wide statistics** (admin)

### 🔔 Notifications
- **Real-time notifications** for uploads, shares, revocations
- **Unread indicator** with animated dot
- **Mark as read** individually or all at once
- **Welcome notification** on registration

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** installed
- **pip** package manager

### Installation

```bash
# 1. Navigate to the project directory
cd c:\Users\rajha\Downloads\AAAA\suro

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the backend (Terminal 1)
python backend/server.py

# 4. Start the frontend (Terminal 2)
python -m streamlit run frontend/app.py --server.port 8501
```

Or simply double-click **`run.bat`** to start both services at once.

### Access the App

| Service | URL |
|---------|-----|
| **Frontend (UI)** | http://localhost:8501 |
| **Backend (API)** | http://localhost:8000 |
| **API Documentation** | http://localhost:8000/docs |

---

## 📱 How to Use

### 1. Register an Account

1. Open http://localhost:8501
2. Click the **"Create Account"** tab
3. Enter your Ethereum wallet address (e.g., `0x1234...`)
4. Choose a username and password
5. Click **"Create Account →"**

### 2. Upload a File

1. Click **"Upload"** in the sidebar
2. Drag-and-drop or browse for a file
3. Add a description and tags (optional)
4. Toggle encryption and blockchain registration
5. Click **"🚀 Upload & Secure"**
6. View the IPFS CID, SHA-256 hash, and blockchain tx hash

### 3. Share a File

1. Click **"Share File"** in the sidebar
2. Select a file from the dropdown
3. Enter the recipient's wallet address
4. Choose access level (VIEW / DOWNLOAD / RESHARE)
5. Set an expiry time (or "Never")
6. Click **"🔗 Grant Access"**

### 4. Verify File Integrity

1. Click **"File Integrity"** in the sidebar
2. Select a file to verify
3. Click **"🔍 Verify Integrity"**
4. The system recomputes the SHA-256 hash and compares it
5. ✅ = file is untampered, ❌ = file may be corrupted

### 5. View Analytics

1. Click **"Analytics"** in the sidebar
2. See storage breakdown by file type (bar chart)
3. See file count distribution (pie chart)
4. View recent activity in a sortable table

### 6. Explore Blockchain

1. Click **"Blockchain"** in the sidebar
2. View network connection status
3. Browse recent transactions with type, block number, and gas
4. Verify any transaction hash



