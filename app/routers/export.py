import base64
import csv
import io
import json

import pandas as pd
import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models_chat import InterviewSession
from app.db.models_project import Project


router = APIRouter()

class ExportRequest(BaseModel):
    ls_url: str
    user_name: str
    password: str
    survey_id: str
    export_type: str
    language_code: str
    response_type: str

@router.post("/export-map")
async def export_map(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    session_key = None
    try:
        session_key = get_session_key(req.user_name, req.password, req.ls_url)
        export64 = export_responses(
            session_key,
            req.survey_id,
            req.export_type,
            req.language_code,
            req.response_type,
            req.ls_url,
        )
        if not export64:
            raise HTTPException(status_code=400, detail="Unable to fetch export.")

        data_bytes = base64.b64decode(export64)
        text = data_bytes.decode("utf-8-sig", errors="replace")

        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            sep = dialect.delimiter
        except Exception:
            sep = ";"

        df = pd.read_csv(io.StringIO(text), sep=sep, engine="python", quoting=csv.QUOTE_MINIMAL)

        target_prefix = "please enter your prolific id here again"
        prolific_col = next((c for c in df.columns if str(c).lower().startswith(target_prefix)), None)
        if prolific_col is None:
            prolific_col = next((c for c in df.columns if "prolific" in str(c).lower()), None)

        if not prolific_col or prolific_col not in df.columns:
            raise HTTPException(status_code=400, detail="No id column found.")

        prolific_series = df[prolific_col].astype(str).fillna("").str.strip()
        prolific_values = sorted({p for p in prolific_series.tolist() if p})

        if not prolific_values:
            raise HTTPException(status_code=400, detail="No profilic values.")

        stmt_sessions = select(InterviewSession.user_id, InterviewSession.project_id).where(
            InterviewSession.user_id.in_(prolific_values)
        )
        res_sessions = await db.execute(stmt_sessions)
        sessions = res_sessions.all()

        prolific_to_project: dict[str, int | None] = {}
        for user_id, project_id in sessions:
            if user_id not in prolific_to_project:
                prolific_to_project[user_id] = project_id

        project_ids = sorted({pid for pid in prolific_to_project.values() if pid is not None})
        project_id_to_slug: dict[int, str] = {}
        if project_ids:
            stmt_projects = select(Project.id, Project.slug).where(Project.id.in_(project_ids))
            res_projects = await db.execute(stmt_projects)
            for pid, slug in res_projects.all():
                project_id_to_slug[pid] = slug

        def map_project_id(prolific_value: str):
            return prolific_to_project.get(prolific_value, None)

        def map_project_slug(prolific_value: str):
            pid = prolific_to_project.get(prolific_value, None)
            if pid is None:
                return ""
            return project_id_to_slug.get(pid, "")

        df["project_id"] = prolific_series.map(map_project_id).fillna("").astype(str)
        df["project_slug"] = prolific_series.map(map_project_slug)

        out_buf = io.StringIO()
        df.to_csv(out_buf, index=False, sep=sep, lineterminator="\n")
        out_bytes = out_buf.getvalue().encode("utf-8-sig")

        return StreamingResponse(
            io.BytesIO(out_bytes),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="limesurvey_data_with_ladderchat_slugs.csv"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    finally:
        if session_key:
            try:
                release_session_key(session_key, req.ls_url)
            except Exception:
                pass


def rpc_request(method, params, url):
    """
    Führt einen JSON-RPC Aufruf an LimeSurvey durch.
    Gibt result zurück oder wirft Exception bei API-Fehler.
    """
    headers = {
        "Content-Type": "application/json",
        "Connection": "Keep-Alive",
    }
    payload = {
        "method": method,
        "params": params,
        "id": 1,
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    resp.raise_for_status()

    j = resp.json()

    # Prüfe auf API-seitigen Fehler
    if j.get("error") is not None:
        raise Exception(f"RPC-Fehler bei Methode {method}: {j['error']}")

    return j.get("result")


def get_session_key(user_name: str, password: str, url: str):
    return rpc_request("get_session_key", [user_name, password], url)


def release_session_key(session_key, url):
    return rpc_request("release_session_key", [session_key], url)


def export_responses(session_key, survey_id, document_type, language_code, response_type, url):
    """
    Ruft export_responses auf und gibt den Base64-String zurück
    (oder ggf. None, falls nichts geliefert wird).
    """
    return rpc_request(
        "export_responses",
        [session_key, survey_id, document_type, language_code, response_type], url
    )

