"""
FastAPI Web Application & Real-time SSE Server.
Provides interactive web dashboard, live monitoring, draft editing, manual contact overrides, and email dispatch.
"""

import asyncio
import json
import logging
import smtplib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .config import Settings, settings
from .models import CandidateProfile, OutreachMessage, OutreachStatus, VerificationSource
from .pipeline import ReferralPipeline
from .job_finder import JobFinder

from .companies import TOP_200_TECH_COMPANIES

logger = logging.getLogger(__name__)

app = FastAPI(title="LinkedIn Referral & Outreach AI Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
TEMPLATES_DIR = Path(__file__).parent / "templates"
active_drafts: List[OutreachMessage] = []
event_subscribers: List[asyncio.Queue] = []
pipeline_running = False

POSITION_DORK_MAP = {
    "recruiter": '("Talent Acquisition" OR "Recruiter" OR "HR")',
    "engineering_manager": '("Engineering Manager" OR "Tech Lead" OR "VP Engineering" OR "Head of Engineering")',
    "technical_sourcer": '("Technical Sourcer" OR "Talent Partner" OR "Staffing")',
    "ai_lead": '("AI Manager" OR "Lead AI Engineer" OR "Head of AI" OR "Director of AI")',
    "executive": '("Director of Engineering" OR "VP of Technology" OR "CTO")',
    "any": '("Talent Acquisition" OR "Recruiter" OR "HR" OR "Engineering Manager" OR "Tech Lead")',
}


class PipelineStartRequest(BaseModel):
    role: str = "AI Engineer"
    location: str = "India"
    date_filter: str = "r604800"  # default to past week
    max_jobs: int = 3
    contacts_per_job: int = 2
    company: Optional[str] = ""
    target_position: Optional[str] = "recruiter"


class DraftUpdateRequest(BaseModel):
    subject: str
    body: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role_title: Optional[str] = None


class EmailVerifyRequest(BaseModel):
    email: str


class SettingsUpdateRequest(BaseModel):
    DRY_RUN: bool = True
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    APOLLO_API_KEY: Optional[str] = None
    HUNTER_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"
    SENDER_NAME: str = "Job Applicant"
    DEFAULT_RESUME_PATH: str = "sample_data/sample_resume.txt"


async def broadcast_event(event_type: str, data: Dict[str, Any]):
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for queue in list(event_subscribers):
        try:
            await queue.put(message)
        except Exception:
            event_subscribers.remove(queue)


def sync_broadcast_log(level: str, msg: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_event("log", {"level": level, "message": msg}))
    except RuntimeError:
        asyncio.run(broadcast_event("log", {"level": level, "message": msg}))


def sync_broadcast_progress(stage: str, percent: int):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_event("progress", {"stage": stage, "percent": percent}))
    except RuntimeError:
        asyncio.run(broadcast_event("progress", {"stage": stage, "percent": percent}))


def sync_broadcast_draft(draft: OutreachMessage):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_event("draft", {"recipient": draft.recipient.email}))
    except RuntimeError:
        asyncio.run(broadcast_event("draft", {"recipient": draft.recipient.email}))


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return index_file.read_text(encoding="utf-8")


@app.get("/api/pipeline/events")
async def sse_events():
    queue = asyncio.Queue()
    event_subscribers.append(queue)

    async def event_generator():
        current_status = "RUNNING" if pipeline_running else "IDLE"
        yield f"event: status\ndata: {json.dumps({'status': current_status})}\n\n"

        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            if queue in event_subscribers:
                event_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


def get_candidate_profile() -> CandidateProfile:
    resume_path = Path(settings.DEFAULT_RESUME_PATH)
    summary = (
        "AI Engineer specializing in Agentic AI frameworks (LangChain/LangGraph), "
        "Snowflake Cortex AI, RAG knowledge pipelines, and autonomous LLM tool calling. "
        "Claude Certified Architect & Developer with proven impact saving 800+ engineering hours across production deployments."
    )
    skills = [
        "Python", "LangChain & LangGraph", "RAG & LLMs",
        "Snowflake Cortex AI", "Multi-Agent Systems", "Docker & CI/CD",
        "PostgreSQL", "dbt"
    ]
    extracted_text = ""

    if resume_path.exists():
        if resume_path.suffix.lower() == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(resume_path))
                for page in reader.pages:
                    extracted_text += page.extract_text() or ""
            except Exception:
                pass
        else:
            try:
                extracted_text = resume_path.read_text(encoding="utf-8")
            except Exception:
                pass

    if extracted_text and ("AI Engineer" in extracted_text or "Generative AI" in extracted_text):
        skills = [
            "Python", "LangChain/LangGraph", "RAG & Vector Search",
            "Snowflake Cortex AI", "Agentic Workflows", "Azure & Docker"
        ]

    return CandidateProfile(
        full_name=settings.SENDER_NAME or "Rohit Raj Gupta",
        email=settings.SENDER_EMAIL or settings.SMTP_USER or "rohitraj14485@gmail.com",
        summary=summary,
        key_skills=skills,
        years_of_experience=2,
        linkedin_url="https://www.linkedin.com/in/rohit-raj-gupta-05aa9821b",
        github_url="https://github.com/gtbRohit14485",
        resume_path=str(resume_path) if resume_path.exists() else None
    )


@app.get("/api/companies")
async def get_companies():
    return {"companies": TOP_200_TECH_COMPANIES}


@app.post("/api/pipeline/start")
async def start_pipeline(req: PipelineStartRequest):
    global pipeline_running, active_drafts
    if pipeline_running:
        raise HTTPException(status_code=400, detail="Pipeline already in progress")

    pipeline_running = True
    await broadcast_event("status", {"status": "RUNNING"})
    candidate = get_candidate_profile()

    pos_dork = POSITION_DORK_MAP.get(
        req.target_position or "recruiter",
        POSITION_DORK_MAP["recruiter"]
    )

    def run_worker():
        global pipeline_running, active_drafts
        try:
            pipeline = ReferralPipeline(config=settings)
            messages = pipeline.run(
                candidate=candidate,
                job_keywords=req.role,
                location=req.location,
                max_jobs=req.max_jobs,
                contacts_per_job=req.contacts_per_job,
                date_filter=req.date_filter,
                company=req.company or "",
                position_dork=pos_dork,
                log_callback=sync_broadcast_log,
                progress_callback=sync_broadcast_progress,
                draft_callback=sync_broadcast_draft
            )
            active_drafts = messages
        except Exception as e:
            sync_broadcast_log(f"Pipeline error: {e}", "ERROR")
        finally:
            pipeline_running = False
            asyncio.run(broadcast_event("status", {"status": "IDLE"}))
            asyncio.run(broadcast_event("draft", {}))

    asyncio.get_event_loop().run_in_executor(None, run_worker)
    return {"status": "started", "role": req.role, "location": req.location, "date_filter": req.date_filter, "company": req.company}


@app.get("/api/drafts")
async def get_drafts():
    return [d.model_dump() for d in active_drafts]


@app.post("/api/drafts/{index}/update")
async def update_draft(index: int, req: DraftUpdateRequest):
    if index < 0 or index >= len(active_drafts):
        raise HTTPException(status_code=404, detail="Draft not found")

    msg = active_drafts[index]
    msg.subject = req.subject
    msg.body = req.body

    if req.first_name:
        msg.recipient.first_name = req.first_name.strip()
    if req.last_name:
        msg.recipient.last_name = req.last_name.strip()
    if req.email:
        msg.recipient.email = req.email.strip()
    if req.role_title:
        msg.recipient.role_title = req.role_title.strip()

    if req.first_name or req.last_name or req.email:
        msg.recipient.verification_source = VerificationSource.MANUAL

    return {"status": "updated", "index": index, "draft": msg.model_dump()}


@app.post("/api/drafts/{index}/regenerate")
async def regenerate_pitch(index: int):
    if index < 0 or index >= len(active_drafts):
        raise HTTPException(status_code=404, detail="Draft not found")

    msg = active_drafts[index]
    candidate = get_candidate_profile()
    pipeline = ReferralPipeline(config=settings)

    new_msg = pipeline.ai_agent.craft_outreach(candidate, msg.job, msg.recipient)
    msg.subject = new_msg.subject
    msg.body = new_msg.body
    return {"status": "regenerated", "subject": msg.subject, "body": msg.body}


@app.post("/api/drafts/{index}/skip")
async def skip_draft(index: int):
    if index < 0 or index >= len(active_drafts):
        raise HTTPException(status_code=404, detail="Draft not found")
    active_drafts[index].status = OutreachStatus.SKIPPED
    return {"status": "skipped", "index": index}


def probe_email_address(email: str) -> Dict[str, Any]:
    if not email or "@" not in email:
        return {"status": "INVALID_FORMAT", "code": 400, "message": "Invalid email format"}

    domain = email.split("@")[1].strip().lower()
    try:
        output = subprocess.check_output(["host", "-t", "MX", domain], text=True)
        lines = output.strip().split("\n")
        mx_host = None
        for line in lines:
            if "mail is handled by" in line:
                mx_host = line.split("mail is handled by")[1].strip().split()[-1].rstrip(".")
                break
        if not mx_host:
            mx_host = domain
    except Exception:
        mx_host = domain

    try:
        with smtplib.SMTP(mx_host, 25, timeout=5) as server:
            server.helo("referralai.studio")
            server.mail("probe@referralai.studio")
            code, resp = server.rcpt(email)
            resp_text = resp.decode("utf-8", errors="ignore")
            if code == 250:
                return {"status": "VALID", "code": code, "message": f"🟢 Valid Address (250 OK: {resp_text.strip()})", "mx": mx_host}
            elif code in [550, 551, 552, 553]:
                return {"status": "INVALID", "code": code, "message": f"🔴 Rejected ({code}: Address does not exist)", "mx": mx_host}
            else:
                return {"status": "AMBIGUOUS", "code": code, "message": f"🟡 Mail Server Response ({code}: {resp_text.strip()})", "mx": mx_host}
    except Exception:
        return {"status": "MX_FOUND", "code": 200, "message": f"🌐 Active MX Server ({mx_host})", "mx": mx_host}


@app.post("/api/verify-email")
async def verify_email_endpoint(req: EmailVerifyRequest):
    sync_broadcast_log(f"Probing SMTP envelope for target address: {req.email}...", "INFO")
    res = probe_email_address(req.email)
    is_success = res.get("status") in ["VALID", "MX_FOUND"]
    sync_broadcast_log(f"Verification result for {req.email}: {res['message']}", "SUCCESS" if is_success else "WARNING")
    return res


@app.post("/api/drafts/{index}/send")
async def send_draft(index: int, req: Optional[DraftUpdateRequest] = None):
    if index < 0 or index >= len(active_drafts):
        raise HTTPException(status_code=404, detail="Draft not found")

    msg = active_drafts[index]
    if req:
        if req.subject:
            msg.subject = req.subject
        if req.body:
            msg.body = req.body
        if req.first_name:
            msg.recipient.first_name = req.first_name.strip()
        if req.last_name:
            msg.recipient.last_name = req.last_name.strip()
        if req.email:
            msg.recipient.email = req.email.strip()
            msg.recipient.verification_source = VerificationSource.MANUAL

    pipeline = ReferralPipeline(config=settings)
    sync_broadcast_log("INFO", f"Dispatching pitch to {msg.recipient.full_name} <{msg.recipient.email}>...")
    
    success = await asyncio.to_thread(pipeline.email_sender.send, msg, resume_path=settings.DEFAULT_RESUME_PATH)

    if not success:
        sync_broadcast_log("ERROR", f"🔴 Dispatch failed for {msg.recipient.email}: {msg.error_message or 'Unknown error'}")
        raise HTTPException(status_code=500, detail=msg.error_message or "Email send failed")

    dest = "Outbox (.eml/.json)" if settings.DRY_RUN else "Recipient Inbox"
    sync_broadcast_log("SUCCESS", f"🟢 Successfully dispatched pitch to {msg.recipient.full_name} <{msg.recipient.email}> -> {dest}")
    return {
        "status": "sent",
        "recipient": msg.recipient.email,
        "destination": dest,
        "mode": "DRY_RUN" if settings.DRY_RUN else "LIVE"
    }


@app.post("/api/drafts/send-all")
async def send_all_drafts():
    if not active_drafts:
        return {"status": "completed", "sent": 0, "failed": 0, "message": "No drafts available"}

    pipeline = ReferralPipeline(config=settings)
    sent_count = 0
    failed_count = 0

    sync_broadcast_log("INFO", f"🚀 Batch sending triggered for {len(active_drafts)} draft(s)...")

    for i, msg in enumerate(active_drafts):
        if msg.status == OutreachStatus.SKIPPED:
            sync_broadcast_log("WARNING", f"⏭️ Skipping draft #{i + 1} for {msg.recipient.email} (Status: SKIPPED)")
            continue

        sync_broadcast_log("INFO", f"Sending draft #{i + 1}/{len(active_drafts)} to {msg.recipient.full_name} <{msg.recipient.email}>...")
        success = await asyncio.to_thread(pipeline.email_sender.send, msg, resume_path=settings.DEFAULT_RESUME_PATH)
        if success:
            sent_count += 1
            dest = "Outbox (.eml/.json)" if settings.DRY_RUN else "Recipient Inbox"
            sync_broadcast_log("SUCCESS", f"🟢 Approved & Sent #{i + 1}: {msg.recipient.full_name} <{msg.recipient.email}> -> {dest}")
        else:
            failed_count += 1
            sync_broadcast_log("ERROR", f"🔴 Send Failed #{i + 1}: {msg.recipient.full_name} <{msg.recipient.email}> - {msg.error_message or 'Unknown error'}")

    sync_broadcast_log("SUCCESS", f"🎉 Batch dispatch completed: {sent_count} sent, {failed_count} failed out of {len(active_drafts)} total.")
    return {"status": "completed", "sent": sent_count, "failed": failed_count}


@app.get("/api/outbox")
async def list_outbox():
    outbox_dir = Path(settings.OUTBOX_DIR)
    if not outbox_dir.exists():
        return []

    json_files = sorted(outbox_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    records = []
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["filename"] = f.name
            records.append(data)
        except Exception:
            pass
    return records


@app.get("/api/settings")
async def get_settings():
    return {
        "DRY_RUN": settings.DRY_RUN,
        "SMTP_HOST": settings.SMTP_HOST,
        "SMTP_PORT": settings.SMTP_PORT,
        "SMTP_USER": settings.SMTP_USER,
        "SENDER_NAME": settings.SENDER_NAME,
        "DEFAULT_RESUME_PATH": settings.DEFAULT_RESUME_PATH,
        "AI_MODEL": settings.AI_MODEL,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY or "",
        "APOLLO_API_KEY": settings.APOLLO_API_KEY or "",
        "HUNTER_API_KEY": settings.HUNTER_API_KEY or "",
        "SERPER_API_KEY": settings.SERPER_API_KEY or "",
        "SMTP_PASSWORD": settings.SMTP_PASSWORD or "",
    }


def persist_settings_to_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    lines = [
        f"DRY_RUN={'true' if settings.DRY_RUN else 'false'}",
        f"DEBUG={'true' if settings.DEBUG else 'false'}",
        f"OUTBOX_DIR={settings.OUTBOX_DIR}",
        f"SMTP_HOST={settings.SMTP_HOST}",
        f"SMTP_PORT={settings.SMTP_PORT}",
        f"SMTP_USER={settings.SMTP_USER}",
        f"SMTP_PASSWORD={settings.SMTP_PASSWORD or ''}",
        f"SENDER_NAME={settings.SENDER_NAME}",
        f"SENDER_EMAIL={settings.SENDER_EMAIL or settings.SMTP_USER}",
        f"DEFAULT_RESUME_PATH={settings.DEFAULT_RESUME_PATH}",
        f"OPENAI_API_KEY={settings.OPENAI_API_KEY or ''}",
        f"OPENAI_BASE_URL={settings.OPENAI_BASE_URL or ''}",
        f"AI_MODEL={settings.AI_MODEL}",
        f"HUNTER_API_KEY={settings.HUNTER_API_KEY or ''}",
        f"APOLLO_API_KEY={settings.APOLLO_API_KEY or ''}",
        f"SERPER_API_KEY={settings.SERPER_API_KEY or ''}",
    ]
    try:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(".env file updated and persisted to disk.")
    except Exception as e:
        logger.warning(f"Could not persist .env file: {e}")


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    settings.DRY_RUN = req.DRY_RUN
    settings.SMTP_HOST = req.SMTP_HOST
    settings.SMTP_PORT = req.SMTP_PORT
    settings.SMTP_USER = req.SMTP_USER
    if req.SMTP_PASSWORD:
        settings.SMTP_PASSWORD = req.SMTP_PASSWORD
    if req.OPENAI_API_KEY:
        settings.OPENAI_API_KEY = req.OPENAI_API_KEY
    if req.APOLLO_API_KEY:
        settings.APOLLO_API_KEY = req.APOLLO_API_KEY
    if req.HUNTER_API_KEY:
        settings.HUNTER_API_KEY = req.HUNTER_API_KEY
    if req.SERPER_API_KEY:
        settings.SERPER_API_KEY = req.SERPER_API_KEY
    settings.AI_MODEL = req.AI_MODEL
    settings.SENDER_NAME = req.SENDER_NAME
    settings.DEFAULT_RESUME_PATH = req.DEFAULT_RESUME_PATH
    
    # Save to .env on disk for persistence across server restarts
    persist_settings_to_env()
    
    return {"status": "saved", "dry_run": settings.DRY_RUN}
