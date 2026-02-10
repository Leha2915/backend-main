from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import List, Literal, Tuple, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field

from app.auth.encryption_service import get_encryption_service, EncryptionService
from app.db.models_chat import InterviewSession
from app.db.models_project import Project
from app.db.models_user import User
from app.db.schemas_project import ProjectCreate, ProjectDetailsOut, ProjectOut
from app.db.session import get_db
from app.routers.auth import get_current_username

logger = logging.getLogger(__name__)


router = APIRouter()


async def id_by_username(username: str, db: AsyncSession) -> int | None:
    res = await db.execute(select(User).where(User.username == username))
    user = res.scalars().first()
    if user is None:
        return None

    return user.id


@router.post("/projects", response_model=ProjectOut)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
    encryption_service: EncryptionService = Depends(get_encryption_service),
):
    import secrets

    user_id = await id_by_username(username, db)

    slug = secrets.token_hex(4)  # z. B. 'abc123ef'

    max_values = -1

    if payload.n_values_max:
        max_values = payload.n_values_max

    project = Project(
        topic=payload.topic,
        description=payload.description,
        stimuli=payload.stimuli,
        n_stimuli=payload.n_stimuli,
        api_key=encryption_service.encrypt(payload.api_key),
        model=payload.model,
        base_url=payload.base_url,
        slug=slug,
        user_id=user_id,
        is_active=True,
        n_values_max=max_values,
        min_nodes=payload.min_nodes,
        voice_enabled=payload.voice_enabled,
        advanced_voice_enabled=payload.advanced_voice_enabled,
        interview_mode=payload.interview_mode,
        tree_enabled=payload.tree_enabled,
        elevenlabs_api_key=encryption_service.encrypt(
        payload.elevenlabs_api_key),
        max_retries=payload.max_retries,
        auto_send=payload.auto_send,
        time_limit=payload.time_limit,
        r2_account_id=payload.r2_account_id,
        r2_access_key_id=encryption_service.encrypt(payload.r2_access_key_id),
        r2_secret_access_key=encryption_service.encrypt(payload.r2_secret_access_key),
        r2_bucket=payload.r2_bucket,  
        language=payload.language,
        grouped={},
        internal_id=payload.internal_id,
        stt_key=encryption_service.encrypt(payload.stt_key),
        stt_endpoint=payload.stt_endpoint
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/test-project", response_model=ProjectOut)
async def create_test_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    encryption_service: EncryptionService = Depends(get_encryption_service),
):
    import secrets

    slug = secrets.token_hex(4)

    # Use the same logic as for the normal /projects route
    max_values = -1
    if payload.n_values_max:
        max_values = payload.n_values_max

    project = Project(
        topic=payload.topic,
        description=payload.description,
        stimuli=payload.stimuli,
        n_stimuli=payload.n_stimuli,
        api_key=encryption_service.encrypt(payload.api_key),
        model=payload.model,
        base_url=payload.base_url,
        slug=slug,
        user_id=1,
        is_active=True,
        n_values_max=max_values,
        min_nodes=payload.min_nodes,
        voice_enabled=payload.voice_enabled,  
        advanced_voice_enabled=payload.advanced_voice_enabled,
        interview_mode=payload.interview_mode,
        tree_enabled=payload.tree_enabled,
        elevenlabs_api_key=encryption_service.encrypt(payload.elevenlabs_api_key),
        max_retries=payload.max_retries,
        auto_send = False,
        time_limit = -1,
        language=payload.language,
        internal_id=payload.internal_id,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects", response_model=List[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    user_id = await id_by_username(username, db)
    res = await db.execute(
        select(Project).where(Project.user_id == user_id)
    )
    return res.scalars().all()


@router.get("/projects/{slug}", response_model=ProjectOut)
async def get_project(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Project).where(Project.slug == slug)
    )
    project = res.scalar()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.is_active:
        raise HTTPException(
            status_code=403, detail="Interviews for this project are closed")

    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: int = Path(...,
                           description="ID of the project to delete"),
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    user_id = await id_by_username(username, db)
    result = await db.execute(
        select(Project).where(Project.id ==
                              project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return None


@router.patch("/projects/{project_id}/toggle", response_model=ProjectOut, status_code=200)
async def toggle_project(
    project_id: int = Path(..., description="ID of the project to toggle"),
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    user_id = await id_by_username(username, db)
    result = await db.execute(
        select(Project).where(Project.id ==
                              project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_active = not project.is_active
    await db.commit()
    await db.refresh(project)

    return ProjectOut.model_validate(project)


@router.get("/projects/{slug}/details", response_model=ProjectDetailsOut)
async def get_project_details(
    slug: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    user_id = await id_by_username(username, db)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    res = await db.execute(
        select(Project).where(Project.slug == slug, Project.user_id == user_id)
    )
    project = res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats_res = await db.execute(
        select(
            func.coalesce(func.count(InterviewSession.id),
                          0).label("sessions_total"),
            func.max(InterviewSession.updated_at).label("last_activity"),
        ).where(InterviewSession.project_id == project.id)
    )
    row = stats_res.first()
    sessions_total = int(
        row.sessions_total) if row and row.sessions_total is not None else 0
    last_activity = row.last_activity if row else None

    return ProjectDetailsOut(
        id=project.id,
        slug=project.slug,
        topic=project.topic,
        description=project.description,
        stimuli=project.stimuli or [],
        n_stimuli=project.n_stimuli,
        model=project.model,
        base_url=project.base_url,
        created_at=project.created_at,
        is_active=project.is_active,
        voice_enabled=project.voice_enabled,
        advanced_voice_enabled=project.advanced_voice_enabled,
        interview_mode=project.interview_mode,
        tree_enabled=project.tree_enabled,

        sessions_total=sessions_total,
        last_activity=last_activity,

        n_values_max=project.n_values_max or None,
        min_nodes=project.min_nodes or None,
        max_retries=project.max_retries,
        auto_send=project.auto_send,
        time_limit=project.time_limit,
        r2_bucket=project.r2_bucket,

        language=project.language,
    )


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return s.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def _emit_bullet(item: str):
    parts = _norm(item).split("\n")
    yield f"- {parts[0]}\n".encode("utf-8")
    for p in parts[1:]:
        yield f"  {p}\n".encode("utf-8")


def _emit_message(msg_no: int, role: str, content: str):
    role = (role or "SYSTEM").upper()
    prefix = f"    [{msg_no}] {role}: "
    lines = _norm(content).split("\n")
    yield f"{prefix}{lines[0]}\n".encode("utf-8")
    cont_indent = " " * len(prefix)
    for line in lines[1:]:
        yield f"{cont_indent}{line}\n".encode("utf-8")


@router.get("/projects/{project_slug}/downloadChats")
async def export_project_txt(
    project_slug: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    user_id = await id_by_username(username, db)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    res = await db.execute(
        select(Project).where(Project.slug ==
                              project_slug, Project.user_id == user_id)
    )
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = await db.execute(
        select(InterviewSession.id, InterviewSession.created_at,
               InterviewSession.chat_data, InterviewSession.user_id)
        .where(InterviewSession.project_id == project.id)
        .order_by(InterviewSession.created_at.asc(), InterviewSession.id.asc())
    )
    sessions = rows.all()

    total_sessions = 0
    total_chats = 0
    for _sid, _created, chat_data, _user_id in sessions:
        if not chat_data:
            continue
        total_sessions += 1
        for cs in (chat_data.get("chat_sessions") or []):
            history = cs.get("chat_history") or []
            if history:
                total_chats += 1

    stimuli_list: list[str] = []
    seen = set()
    if isinstance(getattr(project, "stimuli", None), list):
        for s in project.stimuli:
            if not s:
                continue
            s_str = str(s)
            if s_str not in seen:
                seen.add(s_str)
                stimuli_list.append(s_str)
    else:
        for _sid, _created, chat_data in sessions:
            if not chat_data:
                continue
            for cs in (chat_data.get("chat_sessions") or []):
                s = cs.get("stimulus")
                if not s:
                    continue
                if s not in seen:
                    seen.add(s)
                    stimuli_list.append(s)

    filename = f"interviews_{project_slug}_{datetime.utcnow().date().isoformat()}.txt"

    def stream():
        yield (
            f"Project '{project.topic}'\n"
            f"Exported at: {datetime.utcnow().isoformat()}Z\n"
            f"Sessions: {total_sessions} | Chats: {total_chats}\n"
            f"Description: {project.description or '-'}\n"
            f"Stimuli ({len(stimuli_list)}):\n"
        ).encode("utf-8")
        for s in stimuli_list:
            yield from _emit_bullet(s)
        yield b"\n"

        for sess_id, created_at, chat_data, user_id in sessions:
            if not chat_data:
                continue

            user_id = user_id or ""

            session_id = chat_data.get("session_id") or sess_id
            yield (
                f"Session ID: {session_id}\n"
                f"User ID:    {user_id}\n"
                f"Created:    {created_at.isoformat() if created_at else '-'}\n"
            ).encode("utf-8")

            chat_sessions = chat_data.get("chat_sessions") or []
            for chat_idx, cs in enumerate(chat_sessions):
                stimulus = cs.get("stimulus")
                history = cs.get("chat_history") or []
                if not history:
                    continue

                is_finished = cs.get("is_finished") is True
                status = "finished" if is_finished else "not finished"
                yield (f"--- Chat {chat_idx + 1} ({status}) : {stimulus}\n").encode("utf-8")

                for msg_idx, m in enumerate(history):
                    role = m.get("role") or "system"
                    content = m.get("content") or ""
                    yield from _emit_message(msg_idx + 1, role, content)

            yield b"\n"

    return StreamingResponse(
        stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class GroupProjectsIn(BaseModel):
    slug_a: str = Field(..., description="slug project one")
    slug_b: str = Field(..., description="slug project two")


def _ensure_grouped_list(p: Project) -> None:
    if getattr(p, "grouped", None) is None:
        p.grouped = []
    elif not isinstance(p.grouped, list):
        p.grouped = list(p.grouped or [])


@router.post("/projects/group", response_model=List[ProjectOut], status_code=200)
async def group_projects(
    payload: GroupProjectsIn,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    slug_a = payload.slug_a.strip()
    slug_b = payload.slug_b.strip()

    if slug_a == slug_b:
        raise HTTPException(status_code=400, detail="Cannot group with self.")

    user_id = await id_by_username(username, db)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    res = await db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.slug.in_([slug_a, slug_b]),
        )
    )
    projects = {p.slug: p for p in res.scalars().all()}

    if slug_a not in projects or slug_b not in projects:
        raise HTTPException(status_code=404, detail="At least one project not found")

    a, b = projects[slug_a], projects[slug_b]

    _ensure_grouped_list(a)
    _ensure_grouped_list(b)

    if slug_b not in a.grouped:
        a.grouped = [*a.grouped, slug_b]
    if slug_a not in b.grouped:
        b.grouped = [*b.grouped, slug_a] 

    await db.commit()
    await db.refresh(a)
    await db.refresh(b)
    return [a, b]


@router.post("/projects/ungroup", response_model=List[ProjectOut], status_code=200)
async def ungroup_projects(
    payload: GroupProjectsIn,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    slug_a = payload.slug_a.strip()
    slug_b = payload.slug_b.strip()

    if slug_a == slug_b:
        raise HTTPException(status_code=400, detail="Cannot ungroup self")

    user_id = await id_by_username(username, db)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    res = await db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.slug.in_([slug_a, slug_b]),
        )
    )
    projects = {p.slug: p for p in res.scalars().all()}

    if slug_a not in projects or slug_b not in projects:
        raise HTTPException(status_code=404, detail="At least one project not found")

    a, b = projects[slug_a], projects[slug_b]

    _ensure_grouped_list(a)
    _ensure_grouped_list(b)

    a.grouped = [s for s in a.grouped if s != slug_b]
    b.grouped = [s for s in b.grouped if s != slug_a]

    await db.commit()
    await db.refresh(a)
    await db.refresh(b)

    return [a, b]

class ProjectTotalOut(BaseModel):
    sessions_total: int = Field(..., description="Total number of interview sessions for this project")


@router.get("/projects/{slug}/total", response_model=ProjectTotalOut)
async def get_project_total(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Project).where(Project.slug == slug))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats_res = await db.execute(
        select(func.coalesce(func.count(InterviewSession.id), 0).label("sessions_total"))
        .where(InterviewSession.project_id == project.id)
    )
    row = stats_res.first()
    total = int(row.sessions_total) if row and row.sessions_total is not None else 0

    return ProjectTotalOut(sessions_total=total)

class QuestionOption(BaseModel):
    id: str
    label: str

class QuestionBlock(BaseModel):
    type: Literal["question"] = "question"
    id: str
    prompt: str
    options: Tuple[QuestionOption, QuestionOption]
    required: Optional[bool] = True

class SectionBlock(BaseModel):
    type: Literal["section"] = "section"
    title: str
    body: str

class InfoBlocksResponse(BaseModel):
    blocks: List[SectionBlock | QuestionBlock]

class LegacyInfoResponse(BaseModel):
    info: str


PROJECT_INFO_BLOCKS: dict[str, List[SectionBlock | QuestionBlock]] = {
    "de": [
        SectionBlock(
            title="Zweck der Studie",
            body=(
                "In dieser wissenschaftlichen Studie geht es um die Untersuchung deiner Ziele bei der Nutzung von Smartphones. "
                "Dazu verwenden wir ein Tool zur Durchführung eines Interviews, um zu verstehen, wie Endnutzer Produkte und Services wahrnehmen. "
                "Dabei ist uns besonders wichtig zu erfahren, warum bestimmte Eigenschaften und Features wichtig sind."
            ),
        ),
        SectionBlock(
            title="Ablauf der Studie",
            body=(
                "Diese Studie besteht aus zwei Teilen: einem Interview (Teil 1) und dem Ausfüllen eines Fragebogens (Teil 2). "
                "Bitte versuche, die Studie an einem Stück zu bearbeiten. Solltest du deinen Browser schließen, kannst du das Interview dennoch nahtlos fortsetzen."
            ),
        ),
        SectionBlock(
            title="Das Thema",
            body=(
                "Für die Entwicklung neuer Produkte und Services ist es sehr wichtig, Bedürfnisse und Wünsche von Endnutzern zu ermitteln. "
                "Dafür werden Techniken zur Anforderungserhebung angewendet. Eine solche Technik ist das Laddering Interview. "
                "Bei diesem werden einem Nutzer eine Reihe einfacher Fragen gestellt. Diese sollen helfen zu verstehen, was einem Nutzer wichtig ist "
                "und ganz besonders, warum etwas wichtig ist. Da Mensch-zu-Mensch-Interviews sehr zeitaufwendig sind, wurden verschiedene "
                "computerbasierte Tools entwickelt, um solche Interviews durchzuführen."
            ),
        ),
        SectionBlock(
            title="Deine Aufgabe",
            body=(
                "Stelle dir vor, du wurdest gebeten, bei der Entwicklung einer neuen App für Smartphones zu unterstützen. "
                "Damit diese App perfekt auf dich zugeschnitten ist, führt der Anbieter heute ein kurzes Interview mit dir. "
                "Dieses führst du als potenzieller Nutzer der neuen App mit unserem Tool durch. "
                "Mehrere Fragen werden dich durch das Interview führen. Beantworte die Fragen wahrheitsgemäß und detailliert."
            ),
        ),
        SectionBlock(
            title="Was sind deine Ziele bei der Nutzung deines Smartphones?",
            body=(
                "Dir werden mehrere Fragen gestellt werden. Bitte beantworte diese Fragen nach deinem besten Wissen und Gewissen. "
                "Auf der nächsten Seite findest du noch einmal eine Einführung in die Verwendung des Laddering Interview-Tools."
            ),
        ),
        SectionBlock(
            title="Der KI-Agent",
            body=(
                "Der KI-Agent stellt dir wiederholt Fragen über das Thema. "
                "Ziel der Fragen ist immer, herauszufinden, warum du etwas machst und welche Werte, Emotionen oder Wahrnehmungen dafür ausschlaggebend sind.\n\n"
                "Der Chatbot folgt einer automatisierten Interviewstruktur, die du durch deine Antworten beeinflusst. "
                "Es kann vorkommen, dass nicht alle Reaktionen des Chatbots im aktuellen Gesprächsverlauf sinnvoll erscheinen. "
                "Bitte versuche dennoch, eine passende Antwort zu geben, auch wenn dir eine Frage im aktuellen Kontext ungewöhnlich vorkommt."
            ),
        ),
        SectionBlock(
            title="Beispielinteraktion (Laddering)",
            body=(
                "Interviewer: \"Stell dir eine Situation "
                "vor in der du eine Box voll "
                "Schokolade für den Geburtstag "
                "eines Freundes aussuchst. Welche "
                "Attribute der Schokolade sind bei "
                "der Auswahl für dich relevant?\"\n"
                "Teilnehmer: \"Preis, Verpackung "
                "und Cremigkeit der Schokolade\"\n"
                "Interviewer: \"Warum ist Cremigkeit "
                "der Schokolade wichtig für dich?\"\n"
                "Teilnehmer: \"Weil ich dann den "
                "Geschmack genieße\"\n"
                "Interviewer: \"Und warum ist das "
                "wichtig für dich?\"\n"
                "Teilnehmer: \"Weil es mich glücklich "
                "macht\""
            ),
        ),
        SectionBlock(
            title="Alles klar?",
            body=(
                "Im Folgenden wollen wir kurz prüfen, ob du die Instruktionen für das Experiment verstanden hast. "
                "Bitte beantworte dazu die folgenden Fragen mit Ja oder Nein."
            ),
        ),
        QuestionBlock(
            id="laddering",
            prompt="In diesem Interview wird ein KI-Agent ein Laddering Interview mit dir führen.",
            options=(
                QuestionOption(id="yes", label="Ja"),
                QuestionOption(id="no", label="Nein"),
            ),
            required=True,
        ),
        QuestionBlock(
            id="goals",
            prompt="Wir versuchen dadurch herauszufinden, was deine Ziele bei der Nutzung von Smartphones sind.",
            options=(
                QuestionOption(id="yes", label="Ja"),
                QuestionOption(id="no", label="Nein"),
            ),
            required=True,
        ),
        QuestionBlock(
            id="abort",
            prompt="Wenn eine unerwartete Frage kommt, werde ich das Interview beenden.",
            options=(
                QuestionOption(id="yes", label="Ja"),
                QuestionOption(id="no", label="Nein"),
            ),
            required=True,
        ),
    ],

    "en": [
        SectionBlock(
            title="Purpose of the Study",
            body=(
                "This study aims to explore your goals when using smartphones. "
                "We will use an interview tool to understand how end users perceive different smartphone functionalities. "
                "It is especially important for us to learn why certain features and characteristics matter to you."
            ),
        ),
        SectionBlock(
            title="Procedure of the Study",
            body=(
                "This study consists of two parts: an interview (Part 1) and a questionnaire (Part 2). "
                "Please try to complete the study in one sitting."
            ),
        ),
        SectionBlock(
            title="The Topic",
            body=(
                "For the development of new products, it is crucial to identify the needs and desires of end users. "
                "To achieve this, requirement elicitation techniques are used. One such technique is the Laddering Interview, "
                "in which users are asked a series of simple (why) questions to understand what matters to them — and especially why. "
                "Since human-to-human interviews are very time-consuming, various computer-based tools have been developed to conduct such interviews."
            ),
        ),
        SectionBlock(
            title="Your Task",
            body=(
                "Imagine you have been asked to help develop a new smartphone. "
                "To ensure that this product is perfectly tailored to you, we will conduct a short interview with you today. "
                "You will complete this interview as a potential user of the new smartphone. "
                "Several questions will guide you through the interview. Please answer them truthfully and in detail."
            ),
        ),
        SectionBlock(
            title="The AI Agent",
            body=(
                "The AI agent will repeatedly ask you questions about the topic. "
                "The goal of these questions is always to find out why you do something and which values, emotions, or perceptions play a role."
                "The agent follows an interview structure that you influence through your answers. "
                "It may happen that not all of the agent’s responses make perfect sense in the current conversation. "
                "Please still try to provide a fitting answer, even if a question seems unusual in context."
            ),
        ),
        SectionBlock(
            title="Example Interaction (Laddering)",
            body=(
                "Interviewer: \"Imagine a situation where you are choosing a box of chocolates for a friend's birthday. "
                "Which attributes of the chocolate are relevant for your choice?\"\n"
                "Participant: \"Price, packaging, and creaminess of the chocolate\"\n"
                "Interviewer: \"Why is the creaminess of the chocolate important to you?\"\n"
                "Participant: \"Because then I enjoy the taste\"\n"
                "Interviewer: \"And why is that important to you?\"\n"
                "Participant: \"Because it makes me happy\""
            ),
        ),
        # <<< End new Section
        SectionBlock(
            title="All Clear?",
            body=(
                "Next, we would like to briefly check whether you have understood the instructions for the experiment. "
                "Please answer the following questions with Yes or No."
            ),
        ),
        QuestionBlock(
            id="laddering",
            prompt="In this interview, an AI agent will conduct a Laddering Interview with you.",
            options=(
                QuestionOption(id="yes", label="Yes"),
                QuestionOption(id="no", label="No"),
            ),
            required=True,
        ),
        QuestionBlock(
            id="goals",
            prompt="We aim to find out what your goals are when using smartphones.",
            options=(
                QuestionOption(id="yes", label="Yes"),
                QuestionOption(id="no", label="No"),
            ),
            required=True,
        ),
        QuestionBlock(
            id="abort",
            prompt="If an unexpected question comes up, I will end the interview.",
            options=(
                QuestionOption(id="yes", label="Yes"),
                QuestionOption(id="no", label="No"),
            ),
            required=True,
        ),
    ],
}


@router.get("/projects/{slug}/info", response_model=InfoBlocksResponse)
async def get_project_info(
    lang: Optional[str] = Query(None)
):
    chosen = (lang or "en").split("-")[0]
    blocks = PROJECT_INFO_BLOCKS.get(chosen) or PROJECT_INFO_BLOCKS.get("en")
    if not blocks:
        raise HTTPException(status_code=404, detail="no info available")
    return InfoBlocksResponse(blocks=blocks)