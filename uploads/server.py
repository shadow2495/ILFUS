"""
SecureFileShare — FastAPI Backend  (v2.0)
Full-featured REST API for blockchain-based file storage.
Uses SQLite for zero-config local development.
"""

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile,
    File, Form, Header, Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import jwt
import bcrypt
import uvicorn

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey_change_in_production_!!!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = Path(__file__).parent / "secureshare.db"

app = FastAPI(title="SecureFileShare API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── DATABASE ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id               TEXT PRIMARY KEY,
            wallet_address   TEXT UNIQUE NOT NULL,
            username         TEXT UNIQUE NOT NULL,
            email            TEXT,
            hashed_password  TEXT NOT NULL,
            public_key       TEXT NOT NULL DEFAULT '',
            storage_used     INTEGER DEFAULT 0,
            plan             TEXT DEFAULT 'free',
            is_active        INTEGER DEFAULT 1,
            avatar_url       TEXT DEFAULT '',
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS files (
            id               TEXT PRIMARY KEY,
            owner_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_name        TEXT NOT NULL,
            original_name    TEXT NOT NULL,
            mime_type        TEXT NOT NULL,
            file_size        INTEGER NOT NULL,
            file_hash        TEXT NOT NULL,
            ipfs_cid         TEXT,
            is_encrypted     INTEGER DEFAULT 1,
            version          INTEGER DEFAULT 1,
            tags             TEXT DEFAULT '[]',
            description      TEXT,
            is_deleted       INTEGER DEFAULT 0,
            is_public        INTEGER DEFAULT 0,
            tx_hash          TEXT,
            blockchain_confirmed INTEGER DEFAULT 0,
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS grants (
            id               TEXT PRIMARY KEY,
            file_id          TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            granter_id       TEXT NOT NULL REFERENCES users(id),
            grantee_id       TEXT NOT NULL REFERENCES users(id),
            access_level     TEXT DEFAULT 'VIEW',
            can_reshare      INTEGER DEFAULT 0,
            expires_at       TEXT,
            is_revoked       INTEGER DEFAULT 0,
            tx_hash          TEXT,
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id               TEXT PRIMARY KEY,
            file_id          TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            actor_id         TEXT NOT NULL REFERENCES users(id),
            action           TEXT NOT NULL,
            metadata         TEXT DEFAULT '{}',
            ip_address       TEXT,
            tx_hash          TEXT,
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type             TEXT NOT NULL,
            title            TEXT NOT NULL,
            message          TEXT NOT NULL,
            is_read          INTEGER DEFAULT 0,
            metadata         TEXT DEFAULT '{}',
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS blockchain_txns (
            id               TEXT PRIMARY KEY,
            tx_hash          TEXT NOT NULL,
            tx_type          TEXT NOT NULL,
            related_id       TEXT,
            user_id          TEXT REFERENCES users(id),
            block_number     INTEGER,
            gas_used         INTEGER,
            status           TEXT DEFAULT 'confirmed',
            created_at       TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


init_db()

# ─── PYDANTIC MODELS ────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    wallet_address: str
    username: str
    email: Optional[str] = None
    password: str

class LoginRequest(BaseModel):
    wallet_address: str
    password: str

class ShareRequest(BaseModel):
    file_id: str
    grantee_wallet: str
    access_level: str = "VIEW"
    can_reshare: bool = False
    expires_hours: Optional[int] = None

class UpdateProfileRequest(BaseModel):
    email: Optional[str] = None
    avatar_url: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class BulkDeleteRequest(BaseModel):
    file_ids: List[str]

# ─── AUTH HELPERS ────────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def user_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "wallet": row["wallet_address"],
        "wallet_address": row["wallet_address"],
        "username": row["username"],
        "email": row["email"],
        "public_key": row["public_key"],
        "storage_used_mb": round((row["storage_used"] or 0) / (1024 * 1024), 2),
        "storage_used": row["storage_used"] or 0,
        "plan": row["plan"],
        "avatar_url": row["avatar_url"] or "",
        "created_at": row["created_at"],
    }


def file_to_dict(row) -> dict:
    tags = []
    try:
        tags = json.loads(row["tags"]) if row["tags"] else []
    except (json.JSONDecodeError, TypeError):
        tags = []
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "file_name": row["file_name"],
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "file_size": row["file_size"],
        "file_hash": row["file_hash"],
        "ipfs_cid": row["ipfs_cid"],
        "is_encrypted": bool(row["is_encrypted"]),
        "version": row["version"],
        "tags": tags,
        "description": row["description"],
        "is_public": bool(row["is_public"]),
        "tx_hash": row["tx_hash"],
        "blockchain_confirmed": bool(row["blockchain_confirmed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def generate_fake_cid() -> str:
    return "Qm" + secrets.token_hex(22)

def generate_fake_tx() -> str:
    return "0x" + secrets.token_hex(32)

def generate_block_number() -> int:
    import random
    return random.randint(8_000_000, 9_999_999)

def generate_gas() -> int:
    import random
    return random.randint(21000, 150000)

def create_notification(conn, user_id: str, ntype: str, title: str, message: str, metadata: dict = None):
    conn.execute(
        "INSERT INTO notifications (id, user_id, type, title, message, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, ntype, title, message, json.dumps(metadata or {})),
    )

def record_blockchain_txn(conn, tx_hash: str, tx_type: str, related_id: str, user_id: str):
    conn.execute(
        "INSERT INTO blockchain_txns (id, tx_hash, tx_type, related_id, user_id, block_number, gas_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), tx_hash, tx_type, related_id, user_id, generate_block_number(), generate_gas()),
    )

# ─── AUTH ENDPOINTS ──────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(req: RegisterRequest):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE wallet_address = ? OR username = ?",
        (req.wallet_address, req.username),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Wallet or username already registered")

    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    public_key = "ssh-rsa " + secrets.token_hex(32)

    conn.execute(
        """INSERT INTO users (id, wallet_address, username, email, hashed_password, public_key)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, req.wallet_address, req.username, req.email, hashed, public_key),
    )
    conn.commit()

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # Welcome notification
    create_notification(conn, user_id, "welcome", "Welcome to SecureFileShare! 🎉",
                       f"Hello {req.username}! Your blockchain wallet is connected and ready.")
    conn.commit()
    conn.close()

    return {
        "access_token": create_token(user_id),
        "user": user_to_dict(user),
    }


@app.post("/auth/login")
def login(req: LoginRequest):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE wallet_address = ?", (req.wallet_address,)
    ).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(req.password.encode(), user["hashed_password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": create_token(user["id"]),
        "user": user_to_dict(user),
    }


@app.get("/auth/me")
def get_me(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_to_dict(user)


@app.put("/auth/update-profile")
def update_profile(req: UpdateProfileRequest, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    updates = []
    params = []
    if req.email is not None:
        updates.append("email = ?")
        params.append(req.email)
    if req.avatar_url is not None:
        updates.append("avatar_url = ?")
        params.append(req.avatar_url)
    if updates:
        updates.append("updated_at = datetime('now')")
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user_to_dict(user)


@app.post("/auth/change-password")
def change_password(req: ChangePasswordRequest, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    if not bcrypt.checkpw(req.current_password.encode(), user["hashed_password"].encode()):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE users SET hashed_password = ?, updated_at = datetime('now') WHERE id = ?",
                 (new_hash, user_id))
    conn.commit()
    conn.close()
    return {"message": "Password updated successfully"}


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.get("/dashboard/stats")
def dashboard_stats(user_id: str = Depends(get_current_user_id)):
    conn = get_db()

    total_files = conn.execute(
        "SELECT COUNT(*) as cnt FROM files WHERE owner_id = ? AND is_deleted = 0", (user_id,)
    ).fetchone()["cnt"]

    total_size = conn.execute(
        "SELECT COALESCE(SUM(file_size), 0) as total FROM files WHERE owner_id = ? AND is_deleted = 0", (user_id,)
    ).fetchone()["total"]

    shares_given = conn.execute(
        "SELECT COUNT(*) as cnt FROM grants WHERE granter_id = ?", (user_id,)
    ).fetchone()["cnt"]

    shares_received = conn.execute(
        "SELECT COUNT(*) as cnt FROM grants WHERE grantee_id = ? AND is_revoked = 0", (user_id,)
    ).fetchone()["cnt"]

    encrypted_files = conn.execute(
        "SELECT COUNT(*) as cnt FROM files WHERE owner_id = ? AND is_deleted = 0 AND is_encrypted = 1", (user_id,)
    ).fetchone()["cnt"]

    blockchain_txns = conn.execute(
        "SELECT COUNT(*) as cnt FROM blockchain_txns WHERE user_id = ?", (user_id,)
    ).fetchone()["cnt"]

    unread_notifications = conn.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
    ).fetchone()["cnt"]

    conn.close()

    return {
        "total_files": total_files,
        "storage_used_mb": round(total_size / (1024 * 1024), 2),
        "storage_used_bytes": total_size,
        "shares_given": shares_given,
        "shares_received": shares_received,
        "encrypted_files": encrypted_files,
        "blockchain_txns": blockchain_txns,
        "unread_notifications": unread_notifications,
    }


@app.get("/dashboard/activity")
def dashboard_activity(user_id: str = Depends(get_current_user_id), limit: int = Query(20)):
    conn = get_db()
    rows = conn.execute(
        """SELECT a.*, f.file_name, u.username as actor_name
           FROM audit_logs a
           LEFT JOIN files f ON a.file_id = f.id
           LEFT JOIN users u ON a.actor_id = u.id
           WHERE a.actor_id = ? OR a.file_id IN (SELECT id FROM files WHERE owner_id = ?)
           ORDER BY a.created_at DESC LIMIT ?""",
        (user_id, user_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "file_id": r["file_id"],
            "file_name": r["file_name"],
            "action": r["action"],
            "actor_name": r["actor_name"],
            "tx_hash": r["tx_hash"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/dashboard/storage-breakdown")
def storage_breakdown(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    rows = conn.execute(
        """SELECT
             CASE
               WHEN mime_type LIKE 'image/%' THEN 'Images'
               WHEN mime_type LIKE 'video/%' THEN 'Videos'
               WHEN mime_type LIKE 'audio/%' THEN 'Audio'
               WHEN mime_type LIKE '%pdf%' THEN 'PDFs'
               WHEN mime_type LIKE '%zip%' OR mime_type LIKE '%tar%' OR mime_type LIKE '%rar%' THEN 'Archives'
               WHEN mime_type LIKE '%word%' OR mime_type LIKE '%document%' THEN 'Documents'
               WHEN mime_type LIKE '%sheet%' OR mime_type LIKE '%excel%' THEN 'Spreadsheets'
               WHEN mime_type LIKE '%python%' OR mime_type LIKE '%javascript%' OR mime_type LIKE '%json%' OR mime_type LIKE '%text%' THEN 'Code & Text'
               ELSE 'Other'
             END as category,
             COUNT(*) as file_count,
             COALESCE(SUM(file_size), 0) as total_size
           FROM files
           WHERE owner_id = ? AND is_deleted = 0
           GROUP BY category
           ORDER BY total_size DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [
        {"category": r["category"], "file_count": r["file_count"], "total_size": r["total_size"]}
        for r in rows
    ]


# ─── FILE ENDPOINTS ─────────────────────────────────────────────────────────

@app.get("/files")
def list_files(
    user_id: str = Depends(get_current_user_id),
    search: Optional[str] = Query(None),
    file_type: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("newest"),
):
    conn = get_db()
    query = "SELECT * FROM files WHERE owner_id = ? AND is_deleted = 0"
    params = [user_id]

    if search:
        query += " AND (file_name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if file_type and file_type != "All":
        type_map = {
            "Images": "image/%",
            "Videos": "video/%",
            "Audio": "audio/%",
            "Documents": "%document%",
            "Archives": "%zip%",
            "PDFs": "%pdf%",
        }
        if file_type in type_map:
            query += " AND mime_type LIKE ?"
            params.append(type_map[file_type])

    sort_map = {
        "newest": "created_at DESC",
        "oldest": "created_at ASC",
        "name": "file_name ASC",
        "size": "file_size DESC",
        "size_asc": "file_size ASC",
    }
    query += f" ORDER BY {sort_map.get(sort_by, 'created_at DESC')}"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [file_to_dict(r) for r in rows]


@app.get("/files/search")
def search_files(
    q: str = Query(...),
    user_id: str = Depends(get_current_user_id),
):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM files
           WHERE owner_id = ? AND is_deleted = 0
           AND (file_name LIKE ? OR description LIKE ? OR tags LIKE ?)
           ORDER BY created_at DESC LIMIT 50""",
        (user_id, f"%{q}%", f"%{q}%", f"%{q}%"),
    ).fetchall()
    conn.close()
    return [file_to_dict(r) for r in rows]


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: str = Form(""),
    tags: str = Form("[]"),
    user_id: str = Depends(get_current_user_id),
):
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    file_id = str(uuid.uuid4())
    ipfs_cid = generate_fake_cid()
    tx_hash = generate_fake_tx()

    file_path = UPLOAD_DIR / file_id
    file_path.write_bytes(content)

    conn = get_db()
    conn.execute(
        """INSERT INTO files (id, owner_id, file_name, original_name, mime_type, file_size,
                              file_hash, ipfs_cid, tags, description, tx_hash, blockchain_confirmed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (file_id, user_id, file.filename, file.filename, file.content_type or "application/octet-stream",
         len(content), file_hash, ipfs_cid, tags, description, tx_hash),
    )

    conn.execute(
        "UPDATE users SET storage_used = storage_used + ? WHERE id = ?",
        (len(content), user_id),
    )

    conn.execute(
        "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), file_id, user_id, "UPLOAD", tx_hash),
    )

    record_blockchain_txn(conn, tx_hash, "FILE_UPLOAD", file_id, user_id)

    create_notification(conn, user_id, "upload", "File Uploaded ☁️",
                       f"'{file.filename}' has been encrypted and stored on IPFS.")

    conn.commit()
    conn.close()

    return {
        "id": file_id,
        "file_name": file.filename,
        "cid": ipfs_cid,
        "file_hash": file_hash,
        "size": len(content),
        "tx_hash": tx_hash,
    }


@app.get("/files/{file_id}")
def get_file(file_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    if row["owner_id"] != user_id:
        # Check if user has a grant
        conn2 = get_db()
        grant = conn2.execute(
            "SELECT id FROM grants WHERE file_id = ? AND grantee_id = ? AND is_revoked = 0",
            (file_id, user_id),
        ).fetchone()
        conn2.close()
        if not grant:
            raise HTTPException(status_code=403, detail="Access denied")
    return file_to_dict(row)


@app.delete("/files/{file_id}")
def delete_file(file_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND owner_id = ? AND is_deleted = 0",
        (file_id, user_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    tx_hash = generate_fake_tx()
    conn.execute("UPDATE files SET is_deleted = 1, updated_at = datetime('now') WHERE id = ?", (file_id,))
    conn.execute(
        "UPDATE users SET storage_used = MAX(0, storage_used - ?) WHERE id = ?",
        (row["file_size"], user_id),
    )
    conn.execute(
        "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), file_id, user_id, "DELETE", tx_hash),
    )
    record_blockchain_txn(conn, tx_hash, "FILE_DELETE", file_id, user_id)
    conn.commit()

    # Delete physical file
    phys = UPLOAD_DIR / file_id
    if phys.exists():
        phys.unlink()

    conn.close()
    return {"message": "File deleted", "tx_hash": tx_hash}


@app.post("/files/bulk-delete")
def bulk_delete(req: BulkDeleteRequest, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    deleted = 0
    for fid in req.file_ids:
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND owner_id = ? AND is_deleted = 0",
            (fid, user_id),
        ).fetchone()
        if row:
            tx_hash = generate_fake_tx()
            conn.execute("UPDATE files SET is_deleted = 1 WHERE id = ?", (fid,))
            conn.execute(
                "UPDATE users SET storage_used = MAX(0, storage_used - ?) WHERE id = ?",
                (row["file_size"], user_id),
            )
            conn.execute(
                "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), fid, user_id, "DELETE", tx_hash),
            )
            phys = UPLOAD_DIR / fid
            if phys.exists():
                phys.unlink()
            deleted += 1
    conn.commit()
    conn.close()
    return {"deleted": deleted}


@app.get("/files/{file_id}/download")
def download_file(file_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    # Check ownership or grant
    if row["owner_id"] != user_id:
        grant = conn.execute(
            "SELECT id FROM grants WHERE file_id = ? AND grantee_id = ? AND is_revoked = 0 AND access_level IN ('DOWNLOAD', 'RESHARE')",
            (file_id, user_id),
        ).fetchone()
        if not grant:
            conn.close()
            raise HTTPException(status_code=403, detail="Access denied")

    tx_hash = generate_fake_tx()
    conn.execute(
        "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), file_id, user_id, "DOWNLOAD", tx_hash),
    )
    conn.commit()
    conn.close()

    file_path = UPLOAD_DIR / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=row["original_name"],
        media_type=row["mime_type"],
    )


@app.get("/files/{file_id}/verify")
def verify_file(file_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = UPLOAD_DIR / file_id
    if not file_path.exists():
        return {
            "file_id": file_id,
            "stored_hash": row["file_hash"],
            "computed_hash": None,
            "integrity_valid": False,
            "ipfs_cid": row["ipfs_cid"],
            "blockchain_confirmed": bool(row["blockchain_confirmed"]),
            "error": "Physical file not found",
        }

    content = file_path.read_bytes()
    computed_hash = hashlib.sha256(content).hexdigest()

    return {
        "file_id": file_id,
        "file_name": row["file_name"],
        "stored_hash": row["file_hash"],
        "computed_hash": computed_hash,
        "integrity_valid": computed_hash == row["file_hash"],
        "file_size": row["file_size"],
        "ipfs_cid": row["ipfs_cid"],
        "blockchain_confirmed": bool(row["blockchain_confirmed"]),
        "tx_hash": row["tx_hash"],
    }


@app.get("/files/{file_id}/audit")
def file_audit(file_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    rows = conn.execute(
        """SELECT a.*, u.username as actor_name
           FROM audit_logs a
           LEFT JOIN users u ON a.actor_id = u.id
           WHERE a.file_id = ?
           ORDER BY a.created_at DESC""",
        (file_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "file_id": r["file_id"],
            "action": r["action"],
            "actor_name": r["actor_name"],
            "tx_hash": r["tx_hash"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ─── SHARE ENDPOINTS ────────────────────────────────────────────────────────

@app.post("/share")
def share_file(req: ShareRequest, user_id: str = Depends(get_current_user_id)):
    conn = get_db()

    file_row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND owner_id = ? AND is_deleted = 0",
        (req.file_id, user_id),
    ).fetchone()
    if not file_row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found or not owned by you")

    grantee = conn.execute(
        "SELECT id, username FROM users WHERE wallet_address = ?", (req.grantee_wallet,)
    ).fetchone()
    if not grantee:
        conn.close()
        raise HTTPException(status_code=404, detail="Recipient wallet not found")

    grant_id = str(uuid.uuid4())
    tx_hash = generate_fake_tx()
    expires_at = None
    if req.expires_hours:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=req.expires_hours)).isoformat()

    conn.execute(
        """INSERT INTO grants (id, file_id, granter_id, grantee_id, access_level, can_reshare, expires_at, tx_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (grant_id, req.file_id, user_id, grantee["id"], req.access_level,
         1 if req.can_reshare else 0, expires_at, tx_hash),
    )

    conn.execute(
        "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), req.file_id, user_id, "SHARE", tx_hash),
    )

    record_blockchain_txn(conn, tx_hash, "FILE_SHARE", grant_id, user_id)

    # Notify grantee
    granter = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    create_notification(conn, grantee["id"], "share", "File Shared With You 🔗",
                       f"{granter['username']} shared '{file_row['file_name']}' with you ({req.access_level} access).")

    conn.commit()
    conn.close()

    return {
        "grant_id": grant_id,
        "expires_at": expires_at,
        "tx_hash": tx_hash,
    }


@app.get("/share/received")
def shared_with_me(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    rows = conn.execute(
        """SELECT g.*, f.file_name, f.file_size, f.mime_type, u.username as granter_name
           FROM grants g
           JOIN files f ON g.file_id = f.id
           JOIN users u ON g.granter_id = u.id
           WHERE g.grantee_id = ? AND g.is_revoked = 0
           ORDER BY g.created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "file_id": r["file_id"],
            "file_name": r["file_name"],
            "file_size": r["file_size"],
            "mime_type": r["mime_type"],
            "granter_name": r["granter_name"],
            "access_level": r["access_level"],
            "can_reshare": bool(r["can_reshare"]),
            "expires_at": r["expires_at"],
            "granted_at": r["created_at"],
            "tx_hash": r["tx_hash"],
        }
        for r in rows
    ]


@app.post("/share/{grant_id}/revoke")
def revoke_share(grant_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    grant = conn.execute("SELECT * FROM grants WHERE id = ?", (grant_id,)).fetchone()
    if not grant:
        conn.close()
        raise HTTPException(status_code=404, detail="Grant not found")
    if grant["granter_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized")

    tx_hash = generate_fake_tx()
    conn.execute("UPDATE grants SET is_revoked = 1 WHERE id = ?", (grant_id,))
    conn.execute(
        "INSERT INTO audit_logs (id, file_id, actor_id, action, tx_hash) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), grant["file_id"], user_id, "REVOKE", tx_hash),
    )
    record_blockchain_txn(conn, tx_hash, "ACCESS_REVOKE", grant_id, user_id)
    create_notification(conn, grant["grantee_id"], "revoke", "Access Revoked 🚫",
                       "Your access to a shared file has been revoked.")
    conn.commit()
    conn.close()
    return {"message": "Access revoked", "tx_hash": tx_hash}


@app.get("/share/given")
def shares_given(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    rows = conn.execute(
        """SELECT g.*, f.file_name, u.username as grantee_name, u.wallet_address as grantee_wallet
           FROM grants g
           JOIN files f ON g.file_id = f.id
           JOIN users u ON g.grantee_id = u.id
           WHERE g.granter_id = ?
           ORDER BY g.created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "file_id": r["file_id"],
            "file_name": r["file_name"],
            "grantee_name": r["grantee_name"],
            "grantee_wallet": r["grantee_wallet"],
            "access_level": r["access_level"],
            "can_reshare": bool(r["can_reshare"]),
            "expires_at": r["expires_at"],
            "is_revoked": bool(r["is_revoked"]),
            "tx_hash": r["tx_hash"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ─── BLOCKCHAIN ENDPOINTS ───────────────────────────────────────────────────

@app.get("/blockchain/status")
def blockchain_status(user_id: str = Depends(get_current_user_id)):
    import random
    return {
        "connected": True,
        "network": "Ethereum Sepolia Testnet",
        "chain_id": 11155111,
        "latest_block": generate_block_number(),
        "gas_price_gwei": round(random.uniform(5, 25), 2),
        "contract_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD1e",
        "node_version": "Geth/v1.13.15",
        "peer_count": random.randint(12, 48),
        "syncing": False,
    }


@app.get("/blockchain/transactions")
def blockchain_transactions(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(20),
):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM blockchain_txns
           WHERE user_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "tx_hash": r["tx_hash"],
            "tx_type": r["tx_type"],
            "block_number": r["block_number"],
            "gas_used": r["gas_used"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/blockchain/verify/{tx_hash}")
def verify_transaction(tx_hash: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM blockchain_txns WHERE tx_hash = ?", (tx_hash,)
    ).fetchone()
    conn.close()
    if not row:
        return {"verified": False, "message": "Transaction not found"}
    return {
        "verified": True,
        "tx_hash": row["tx_hash"],
        "tx_type": row["tx_type"],
        "block_number": row["block_number"],
        "gas_used": row["gas_used"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ─── NOTIFICATIONS ──────────────────────────────────────────────────────────

@app.get("/notifications")
def get_notifications(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(30),
):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "title": r["title"],
            "message": r["message"],
            "is_read": bool(r["is_read"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notif_id, user_id),
    )
    conn.commit()
    conn.close()
    return {"message": "Marked as read"}


@app.post("/notifications/read-all")
def mark_all_read(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,),
    )
    conn.commit()
    conn.close()
    return {"message": "All notifications marked as read"}


# ─── ADMIN ───────────────────────────────────────────────────────────────────

@app.get("/admin/system-stats")
def system_stats(user_id: str = Depends(get_current_user_id)):
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
    total_files = conn.execute("SELECT COUNT(*) as cnt FROM files WHERE is_deleted = 0").fetchone()["cnt"]
    total_storage = conn.execute("SELECT COALESCE(SUM(file_size), 0) as total FROM files WHERE is_deleted = 0").fetchone()["total"]
    total_shares = conn.execute("SELECT COUNT(*) as cnt FROM grants").fetchone()["cnt"]
    total_txns = conn.execute("SELECT COUNT(*) as cnt FROM blockchain_txns").fetchone()["cnt"]
    conn.close()
    return {
        "total_users": total_users,
        "total_files": total_files,
        "total_storage_mb": round(total_storage / (1024 * 1024), 2),
        "total_shares": total_shares,
        "total_blockchain_txns": total_txns,
    }


# ─── HEALTH ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0", "service": "SecureFileShare API"}


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    print(f"\n  [SecureFileShare API v2.0]")
    print(f"  |-- Listening on http://0.0.0.0:{port}")
    print(f"  |-- Database: {DB_PATH}")
    print(f"  +-- Uploads:  {UPLOAD_DIR}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)

