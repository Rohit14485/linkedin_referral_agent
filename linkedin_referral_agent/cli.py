"""
Interactive Command-Line Interface (CLI).
Provides rich terminal dashboard, draft preview, and interactive approval workflow.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .config import settings
from .models import CandidateProfile, ContactRole, OutreachMessage, OutreachStatus
from .pipeline import ReferralPipeline
from .email_sender import EmailSender

console = Console()


def load_candidate_from_file(resume_path: str) -> CandidateProfile:
    path = Path(resume_path)
    if not path.exists():
        console.print(f"[yellow]Resume file not found at {path}. Using default profile.[/yellow]")
        return CandidateProfile(
            full_name=settings.SENDER_NAME or "Job Applicant",
            email=settings.SENDER_EMAIL or "applicant@example.com",
            summary="Experienced Software Engineer specialized in distributed systems, backend APIs, and cloud services.",
            key_skills=["Python", "Go", "Distributed Systems", "APIs", "Docker", "PostgreSQL"],
            years_of_experience=5,
            resume_path=None
        )

    text = path.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = lines[0] if lines else settings.SENDER_NAME

    # Extract email if present
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    email = email_match.group(0) if email_match else (settings.SENDER_EMAIL or "applicant@example.com")

    # Extract LinkedIn URL if present
    li_match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[\w-]+", text)
    linkedin_url = li_match.group(0) if li_match else None

    # Extract SUMMARY section
    summary = "Experienced Software Engineer specialized in high-concurrency distributed systems and cloud services."
    if "SUMMARY" in text:
        after_summary = text.split("SUMMARY", 1)[1]
        summary_lines = []
        for line in after_summary.strip().splitlines():
            line_str = line.strip()
            if any(sec in line_str.upper() for sec in ["KEY SKILLS", "EXPERIENCE", "EDUCATION"]):
                break
            if line_str:
                summary_lines.append(line_str)
        if summary_lines:
            summary = " ".join(summary_lines)

    # Extract SKILLS
    skills = ["Python", "Distributed Systems", "APIs", "Kubernetes", "PostgreSQL"]
    if "KEY SKILLS" in text:
        after_skills = text.split("KEY SKILLS", 1)[1]
        extracted_skills = []
        for line in after_skills.strip().splitlines():
            if any(sec in line.strip().upper() for sec in ["EXPERIENCE", "EDUCATION"]):
                break
            # Look for words or comma separated lists
            cleaned = re.sub(r"^[-*•]\s*", "", line.strip())
            cleaned = re.sub(r"^(Languages|Frameworks & Tools|AI & LLM Engineering):\s*", "", cleaned)
            for part in cleaned.split(","):
                part_clean = part.strip()
                if part_clean and len(part_clean) > 1:
                    extracted_skills.append(part_clean)
        if extracted_skills:
            skills = extracted_skills[:6]

    return CandidateProfile(
        full_name=name,
        email=email,
        linkedin_url=linkedin_url,
        summary=summary,
        key_skills=skills,
        years_of_experience=5,
        resume_path=str(path)
    )


def display_message_card(msg: OutreachMessage, index: int, total: int):
    role_badge = (
        "[bold cyan]RECRUITER[/bold cyan]"
        if msg.recipient.role_category == ContactRole.RECRUITER
        else "[bold magenta]HIRING MANAGER[/bold magenta]"
    )

    header = (
        f"[bold white]Draft {index}/{total}[/bold white] | "
        f"[bold yellow]{msg.job.company_name}[/bold yellow] - {msg.job.title}\n"
        f"Recipient: [bold green]{msg.recipient.full_name}[/bold green] ({msg.recipient.role_title}) {role_badge}\n"
        f"Email: [underline]{msg.recipient.email}[/underline] | Confidence: {int(msg.recipient.confidence_score * 100)}%\n"
        f"Job Link: [blue]{msg.job.job_url}[/blue]"
    )

    body_preview = (
        f"[bold cyan]Subject:[/bold cyan] {msg.subject}\n\n"
        f"[bold cyan]Message Body:[/bold cyan]\n"
        f"{msg.body}"
    )

    console.print(Panel(f"{header}\n\n{'-'*60}\n\n{body_preview}", title="Outreach Proposal", border_style="blue"))


def run_interactive_session(
    pipeline: ReferralPipeline,
    candidate: CandidateProfile,
    role: str,
    location: str,
    max_jobs: int,
    contacts_per_job: int,
    auto_approve: bool = False
):
    mode_str = "[green]DRY-RUN (Safe: saves to outbox/)[/green]" if pipeline.config.DRY_RUN else "[bold red]LIVE SMTP (Will send real emails)[/bold red]"
    console.print(Panel.fit(
        f"[bold white]LinkedIn Referral & Outreach AI Agent[/bold white]\n"
        f"Target Role: [bold yellow]{role}[/bold yellow] | Location: [bold yellow]{location}[/bold yellow]\n"
        f"Mode: {mode_str}\n"
        f"Candidate: [bold cyan]{candidate.full_name}[/bold cyan] ({candidate.years_of_experience}+ yrs exp)",
        border_style="green"
    ))

    with console.status("[bold green]Discovering jobs and generating AI referral drafts..."):
        messages = pipeline.run(
            candidate=candidate,
            job_keywords=role,
            location=location,
            max_jobs=max_jobs,
            contacts_per_job=contacts_per_job
        )

    if not messages:
        console.print("[red]No candidate outreach drafts could be created.[/red]")
        return

    console.print(f"\n[bold green]✓ Generated {len(messages)} tailored referral pitches across target companies.[/bold green]\n")

    summary_stats = {"SENT": 0, "SKIPPED": 0, "FAILED": 0}

    for idx, msg in enumerate(messages, 1):
        display_message_card(msg, idx, len(messages))

        if auto_approve:
            action = "a"
            console.print("[dim]Auto-approving draft...[/dim]")
        else:
            action = Prompt.ask(
                "[bold yellow]Action[/bold yellow]",
                choices=["a", "s", "e", "q"],
                default="a"
            ).lower()

        if action == "q":
            console.print("[yellow]Aborting session.[/yellow]")
            break
        elif action == "s":
            msg.status = OutreachStatus.SKIPPED
            summary_stats["SKIPPED"] += 1
            console.print("[dim]Skipped message.[/dim]\n")
        elif action == "e":
            new_subject = Prompt.ask("Edit Subject", default=msg.subject)
            console.print("Enter new message body:")
            new_body = Prompt.ask("Edit Body", default=msg.body)
            msg.subject = new_subject
            msg.body = new_body
            # Send after edit
            success = pipeline.email_sender.send(msg, resume_path=candidate.resume_path)
            if success:
                summary_stats["SENT"] += 1
                console.print("[green]✓ Updated draft processed successfully![/green]\n")
            else:
                summary_stats["FAILED"] += 1
                console.print(f"[red]✗ Failed: {msg.error_message}[/red]\n")
        elif action == "a":
            success = pipeline.email_sender.send(msg, resume_path=candidate.resume_path)
            if success:
                summary_stats["SENT"] += 1
                dest = "Outbox (.eml/.json)" if pipeline.config.DRY_RUN else "Recipient Inbox"
                console.print(f"[green]✓ Dispatched to {dest} for {msg.recipient.email}[/green]\n")
            else:
                summary_stats["FAILED"] += 1
                console.print(f"[red]✗ Failed: {msg.error_message}[/red]\n")

    # Render Summary Table
    table = Table(title="Outreach Session Summary")
    table.add_column("Status", style="bold")
    table.add_column("Count", style="cyan")
    table.add_row("Processed / Dispatched", str(summary_stats["SENT"]))
    table.add_row("Skipped", str(summary_stats["SKIPPED"]))
    table.add_row("Failed", str(summary_stats["FAILED"]))
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Referral & Outreach AI Agent")
    parser.add_argument("--role", type=str, default="Software Engineer", help="Job keywords to search")
    parser.add_argument("--location", type=str, default="Remote", help="Location filter")
    parser.add_argument("--max-jobs", type=int, default=3, help="Maximum jobs to inspect")
    parser.add_argument("--contacts-per-job", type=int, default=2, help="Contacts per job (HR / Manager)")
    parser.add_argument("--resume", type=str, default="sample_data/sample_resume.txt", help="Path to resume")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Force dry-run outbox mode")
    parser.add_argument("--live", action="store_true", help="Enable live SMTP dispatch")
    parser.add_argument("--auto-approve", action="store_true", help="Auto approve drafts without prompt")

    args = parser.parse_args()

    if args.live:
        settings.DRY_RUN = False
    elif args.dry_run:
        settings.DRY_RUN = True

    candidate = load_candidate_from_file(args.resume)
    pipeline = ReferralPipeline(config=settings)

    run_interactive_session(
        pipeline=pipeline,
        candidate=candidate,
        role=args.role,
        location=args.location,
        max_jobs=args.max_jobs,
        contacts_per_job=args.contacts_per_job,
        auto_approve=args.auto_approve
    )


if __name__ == "__main__":
    main()
