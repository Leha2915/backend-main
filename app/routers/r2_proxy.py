import os, hashlib, boto3
import re
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body, Query
from fastapi.responses import JSONResponse
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from botocore.exceptions import ClientError
from app.db.session import get_db
from botocore.config import Config
from sqlalchemy import func, select
from app.db.models_project import Project

from app.auth.encryption_service import get_encryption_service, EncryptionService

from typing import Optional, List, Dict, Any

router = APIRouter()

def build_r2_endpoint(account_id: str) -> str:
    return f"https://{account_id}.eu.r2.cloudflarestorage.com"

def make_s3_client(
    account_id: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
):
    account_id = account_id.strip()
    access_key_id = access_key_id.strip()
    secret_access_key = secret_access_key.strip()

    if not account_id or not access_key_id or not secret_access_key:
        raise ValueError("Missing R2 credentials (account_id/access_key_id/secret_access_key).")

    endpoint_url = build_r2_endpoint(account_id)

    cfg = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )

    return boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=cfg,
    )

ACCOUNT_ID_RE = re.compile(r"^[a-fA-F0-9]{32}$")

def test_account_id_format(account_id: str) -> dict:
    ok = bool(ACCOUNT_ID_RE.match((account_id or "").strip()))
    return {"ok": ok, "reason": None if ok else "Account ID must be 32 hex characters (0-9, a-f)."}

def test_credentials_basic(s3) -> dict:
    try:
        s3.list_buckets()
        return {"ok": True}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
            return {"ok": False, "reason": f"Invalid credentials: {code}"}
        if code == "AccessDenied":
            return {"ok": True, "warning": "Credentials valid, but access to list buckets is denied"}
        return {"ok": False, "reason": f"Unexpected error: {code}"}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def test_bucket_access(s3, bucket: str) -> dict:
    if not bucket:
        return {"ok": False, "reason": "Bucket name is required."}
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        status = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        code = (e.response.get("Error", {}) or {}).get("Code", "")
        if status == 404 or code in ("NoSuchBucket", "NotFound"):
            return {"ok": False, "reason": f"Bucket \"{bucket}\" not found."}
        if status == 403 or code in ("AccessDenied", "Forbidden"):
            return {"ok": False, "reason": f"No access to bucket \"{bucket}\" with provided credentials."}
        return {"ok": False, "reason": f"Bucket check failed: {code or status}"}
    try:
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
    except ClientError as e:
        return {"ok": True, "note": f"Bucket exists, but listing failed: {e.response.get('Error', {}).get('Code')}"}
    return {"ok": True}

def head_exists(s3, bucket: str, key: str):
    try:
        resp = s3.head_object(Bucket=bucket, Key=key)
        return True, resp
    except ClientError as e:
        code = str(e.response.get("Error", {}).get("Code", "")).upper()
        status = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if code in ("404", "NOSUCHKEY", "NOTFOUND") or status == 404:
            return False, None
        if status == 403 or code == "ACCESSDENIED":
            raise
        raise

def sha256_hex_of_upload(upload: UploadFile) -> str:
    h = hashlib.sha256()
    upload.file.seek(0)
    while chunk := upload.file.read(1024 * 1024):
        h.update(chunk)
    upload.file.seek(0)
    return h.hexdigest()

@router.post("/cloudflare/test")
async def cloudflare_test(
    payload: dict = Body(...),
):
    test = (payload.get("test") or "").strip()
    account_id = (payload.get("accountId") or "").strip()
    access_key_id = (payload.get("accessKeyId") or "").strip()
    secret_access_key = (payload.get("secretAccessKey") or "").strip()
    bucket = (payload.get("bucket") or "").strip()

    if test == "accountId":
        res = test_account_id_format(account_id)
        return JSONResponse(res, status_code=200 if res["ok"] else 400)

    if test == "credentials":
        acc = test_account_id_format(account_id)
        if not acc["ok"]:
            return JSONResponse({"ok": False, "reason": acc["reason"]}, status_code=400)
        try:
            s3 = make_s3_client(account_id, access_key_id, secret_access_key)
        except Exception as e:
            return JSONResponse({"ok": False, "reason": str(e)}, status_code=400)

        res = test_credentials_basic(s3)
        return JSONResponse(res, status_code=200 if res["ok"] else 401)

    if test == "bucket":
        acc = test_account_id_format(account_id)
        if not acc["ok"]:
            return JSONResponse({"ok": False, "reason": acc["reason"]}, status_code=400)
        if not bucket:
            return JSONResponse({"ok": False, "reason": "Bucket name is required."}, status_code=400)
        try:
            s3 = make_s3_client(account_id, access_key_id, secret_access_key)
        except Exception as e:
            return JSONResponse({"ok": False, "reason": str(e)}, status_code=400)

        res = test_bucket_access(s3, bucket)
        return JSONResponse(res, status_code=200 if res["ok"] else 400)

    return JSONResponse({"ok": False, "reason": "Unknown test. Use 'accountId' | 'credentials' | 'bucket'."}, status_code=400)

    
@router.post("/uploads/audio")
async def upload_audio(
    file: UploadFile = File(...),
    filename: str = Form(...),
    mime_type: str = Form(...),
    size_bytes: str = Form(...),
    duration_sec: str = Form(...),
    project_slug: str = Form(""),
    interview_session_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    
    res = await db.execute(
        select(Project).where(Project.slug == project_slug)
    )
    project = res.scalar()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    account_id = project.r2_account_id
    access_key_id = enc.decrypt(project.r2_access_key_id)
    secret_access_key = enc.decrypt(project.r2_secret_access_key or "") 
    bucket = project.r2_bucket

    if not (account_id and access_key_id and secret_access_key and bucket):
        print("WARNING, CLOUDFLARE CONFIG INVALID OR MISSING")
        return

    s3 = make_s3_client(account_id, access_key_id, secret_access_key)

    safe_project = (project_slug or "no-project").strip().replace("/", "_")
    safe_session = (interview_session_id or "no-session").strip().replace("/", "_")
    original_name = os.path.basename(filename)
    ts_iso = datetime.utcnow().isoformat(timespec="seconds").replace(":", "-")

    sha256_hex = sha256_hex_of_upload(file)
    short = sha256_hex[:12]
    ext = os.path.splitext(original_name)[1] or ""
    key = f"audio/{safe_project}/{safe_session}/{short}{ext or '-' + original_name}"

    try:
        exists, head = head_exists(s3, bucket, key)
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"HEAD failed: {e}")

    if exists:
        return JSONResponse({
            "ok": True,
            "already_exists": True,
            "key": key,
            "hash_sha256": sha256_hex,
            "etag": head.get("ETag", "").strip('"'),
            "size_bytes_on_r2": head.get("ContentLength"),
        })

    extra = {
        "ContentType": mime_type or "audio/mpeg",
        "Metadata": {
            "project-slug": safe_project,
            "interview-session-id": safe_session,
            "duration-sec": str(duration_sec),
            "size-bytes": str(size_bytes),
            "original-filename": original_name,
            "uploaded-at": ts_iso,
            "hash-sha256": sha256_hex,
        },
    }

    try:
        s3.upload_fileobj(file.file, bucket, key, ExtraArgs=extra)
        head = s3.head_object(Bucket=bucket, Key=key)
        return JSONResponse({
            "ok": True,
            "already_exists": False,
            "key": key,
            "hash_sha256": sha256_hex,
            "etag": head.get("ETag", "").strip('"'),
            "size_bytes_on_r2": head.get("ContentLength"),
        })
    except ClientError as e:
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            return JSONResponse({
                "ok": True,
                "already_exists": True,
                "key": key,
                "hash_sha256": sha256_hex,
                "etag": head.get("ETag", "").strip('"'),
                "size_bytes_on_r2": head.get("ContentLength"),
            })
        except Exception:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        

@router.get("/uploads/audio")
async def list_audios_for_session(
    project_slug: str = Query(..., description="project slug"),
    interview_session_id: str = Query(..., description="user specific session id"),
    max_keys: int = Query(100, ge=1, le=1000, description="max keys per page"),
    continuation_token: Optional[str] = Query(None, description="pagnation token"),
    include_metadata: bool = Query(True, description="head meta data"),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):

    res = await db.execute(select(Project).where(Project.slug == project_slug))
    project = res.scalar()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    account_id = project.r2_account_id
    access_key_id = enc.decrypt(project.r2_access_key_id)
    secret_access_key = enc.decrypt(project.r2_secret_access_key)
    bucket = project.r2_bucket

    if not (account_id and access_key_id and secret_access_key and bucket):
        raise HTTPException(status_code=500, detail="Cloudflare R2 config invalid or missing")

    try:
        s3 = make_s3_client(account_id, access_key_id, secret_access_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"S3 client error: {e}")

    safe_project = (project_slug or "no-project").strip().replace("/", "_")
    safe_session = (interview_session_id or "no-session").strip().replace("/", "_")
    prefix = f"audio/{safe_project}/{safe_session}/"

    list_kwargs: Dict[str, Any] = {
        "Bucket": bucket,
        "Prefix": prefix,
        "MaxKeys": max_keys,
    }
    if continuation_token:
        list_kwargs["ContinuationToken"] = continuation_token

    try:
        resp = s3.list_objects_v2(**list_kwargs)
    except ClientError as e:
        code = (e.response.get("Error", {}) or {}).get("Code", "Unknown")
        raise HTTPException(status_code=502, detail=f"List failed: {code}")

    contents: List[Dict[str, Any]] = []
    for obj in resp.get("Contents", []) or []:
        key = obj.get("Key")
        if not key or not key.startswith(prefix):
            continue

        item = {
            "key": key,
            "size_bytes_on_r2": obj.get("Size"),
            "etag": (obj.get("ETag") or "").strip('"'),
            "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
            "storage_class": obj.get("StorageClass"),
            "metadata": None,
        }

        if include_metadata:
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                md = head.get("Metadata", {}) or {}
                item["metadata"] = {
                    "project-slug": md.get("project-slug"),
                    "interview-session-id": md.get("interview-session-id"),
                    "duration-sec": md.get("duration-sec"),
                    "size-bytes": md.get("size-bytes"),
                    "original-filename": md.get("original-filename"),
                    "uploaded-at": md.get("uploaded-at"),
                    "hash-sha256": md.get("hash-sha256"),
                    "content_type": head.get("ContentType"),
                }
                item["etag"] = (head.get("ETag") or "").strip('"') or item["etag"]
                item["size_bytes_on_r2"] = head.get("ContentLength") or item["size_bytes_on_r2"]
            except ClientError as e:
                item["metadata"] = None

        contents.append(item)

    result = {
        "ok": True,
        "count": len(contents),
        "prefix": prefix,
        "items": contents,
        "is_truncated": bool(resp.get("IsTruncated")),
        "next_continuation_token": resp.get("NextContinuationToken"),
    }

    print(JSONResponse(result))
    return JSONResponse(result)


@router.get("/uploads/audio/signed-url")
async def get_signed_audio_url(
    project_slug: str = Query(...),
    interview_session_id: str = Query(...),
    key: str = Query(...),
    expires_sec: int = Query(300, ge=60, le=3600),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    res = await db.execute(select(Project).where(Project.slug == project_slug))
    project = res.scalar()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    account_id = project.r2_account_id
    access_key_id = enc.decrypt(project.r2_access_key_id)
    secret_access_key = enc.decrypt(project.r2_secret_access_key)
    bucket = project.r2_bucket
    if not (account_id and access_key_id and secret_access_key and bucket):
        raise HTTPException(status_code=500, detail="Cloudflare R2 config invalid or missing")

    s3 = make_s3_client(account_id, access_key_id, secret_access_key)

    safe_project = (project_slug or "no-project").strip().replace("/", "_")
    safe_session = (interview_session_id or "no-session").strip().replace("/", "_")
    allowed_prefix = f"audio/{safe_project}/{safe_session}/"
    if not key or not key.startswith(allowed_prefix):
        raise HTTPException(status_code=403, detail="Key not allowed for this session")

    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        raise HTTPException(status_code=404, detail="Object not found")

    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_sec,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not sign URL: {e}")

    return JSONResponse({"ok": True, "url": url, "expires_in": expires_sec})