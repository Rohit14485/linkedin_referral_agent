from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Callable, List, Optional
from pathlib import Path

from .config import Settings, settings
from .models import CandidateProfile, JobPosting, ContactPerson, OutreachMessage
from .job_finder import JobFinder
from .contact_finder import ContactFinder
from .ai_agent import OutreachAgent
from .email_sender import EmailSender

logger = logging.getLogger(__name__)


class ReferralPipeline:
    def __init__(
        self,
        config: Optional[Settings] = None,
        job_finder: Optional[JobFinder] = None,
        contact_finder: Optional[ContactFinder] = None,
        ai_agent: Optional[OutreachAgent] = None,
        email_sender: Optional[EmailSender] = None,
    ):
        self.config = config or settings
        self.job_finder = job_finder or JobFinder()
        self.contact_finder = contact_finder or ContactFinder(
            hunter_api_key=self.config.HUNTER_API_KEY,
            apollo_api_key=self.config.APOLLO_API_KEY,
            serper_api_key=self.config.SERPER_API_KEY
        )
        self.ai_agent = ai_agent or OutreachAgent(
            api_key=self.config.OPENAI_API_KEY,
            base_url=self.config.OPENAI_BASE_URL,
            model=self.config.AI_MODEL
        )
        self.email_sender = email_sender or EmailSender(
            smtp_host=self.config.SMTP_HOST,
            smtp_port=self.config.SMTP_PORT,
            smtp_user=self.config.SMTP_USER,
            smtp_password=self.config.SMTP_PASSWORD,
            sender_name=self.config.SENDER_NAME,
            sender_email=self.config.SENDER_EMAIL,
            dry_run=self.config.DRY_RUN,
            outbox_dir=Path(self.config.OUTBOX_DIR)
        )

    def run(
        self,
        candidate: CandidateProfile,
        job_keywords: str,
        location: str = "India",
        max_jobs: int = 3,
        contacts_per_job: int = 2,
        date_filter: Optional[str] = "r604800",
        company: Optional[str] = "",
        position_dork: Optional[str] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        draft_callback: Optional[Callable[[OutreachMessage], None]] = None,
    ) -> List[OutreachMessage]:
        """
        Executes parallelized job search, contact discovery, and AI pitch generation.
        """
        def emit_log(msg: str, level: str = "INFO"):
            logger.info(msg)
            if log_callback:
                try:
                    log_callback(level, msg)
                except Exception:
                    pass

        def emit_progress(stage: str, percent: int):
            if progress_callback:
                try:
                    progress_callback(stage, percent)
                except Exception:
                    pass

        date_label_map = {
            "r3600": "Past 1 Hour",
            "past_1h": "Past 1 Hour",
            "r21600": "Past 6 Hours",
            "past_6h": "Past 6 Hours",
            "r43200": "Past 12 Hours",
            "past_12h": "Past 12 Hours",
            "r86400": "Past 24 Hours",
            "past_24h": "Past 24 Hours",
            "r604800": "Past Week",
            "past_week": "Past Week",
            "r2592000": "Past Month",
            "past_month": "Past Month",
            "": "Any Time",
            "any": "Any Time"
        }
        date_label = date_label_map.get(date_filter or "", "Any Time")

        search_query = f"{job_keywords} {company}".strip() if company else job_keywords
        co_log = f" at company '{company}'" if company else ""

        emit_progress("Searching LinkedIn Jobs", 10)
        emit_log(f"Searching LinkedIn for '{search_query}' in region: '{location}'{co_log} (Date Posted: {date_label})...")

        jobs = self.job_finder.search_jobs(
            keywords=search_query,
            location=location,
            limit=max_jobs,
            date_filter=date_filter
        )
        emit_log(f"Discovered {len(jobs)} relevant job listings from LinkedIn.")
        emit_progress("Analyzing & Pitching via Parallel Workers", 30)

        messages: List[OutreachMessage] = []
        total_jobs = len(jobs)
        completed_count = 0

        def process_job(job_tuple):
            idx, job = job_tuple
            date_info = f" (Posted: {job.posted_date})" if job.posted_date else ""
            emit_log(f"[{idx}/{total_jobs}] Found {job.title} at {job.company_name} ({job.location}){date_info}")
            
            contacts = self.contact_finder.find_contacts_for_job(
                job, max_contacts=contacts_per_job, position_dork=position_dork
            )
            emit_log(f"Identified {len(contacts)} talent & management contacts for {job.company_name}.")

            job_msgs = []
            for contact in contacts:
                emit_log(f"Generating AI pitch for {contact.full_name} ({contact.role_title})...")
                msg = self.ai_agent.craft_outreach(candidate, job, contact)
                job_msgs.append(msg)
                if draft_callback:
                    try:
                        draft_callback(msg)
                    except Exception:
                        pass
            return idx, job_msgs

        # Use ThreadPoolExecutor to process jobs & contact discovery in parallel!
        max_workers = min(8, max(1, total_jobs))
        emit_log(f"Spinning up {max_workers} parallel workers to accelerate discovery & pitching...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {executor.submit(process_job, (i, job)): (i, job) for i, job in enumerate(jobs, 1)}
            
            # Preserve original job order in result list
            results_dict = {}
            for future in as_completed(future_to_job):
                try:
                    idx, job_msgs = future.result()
                    results_dict[idx] = job_msgs
                except Exception as e:
                    logger.warning(f"Error in worker thread: {e}")
                
                completed_count += 1
                current_pct = int(30 + (completed_count / max(total_jobs, 1)) * 65)
                emit_progress("Drafting AI Referral Pitches", min(current_pct, 95))

            for i in sorted(results_dict.keys()):
                messages.extend(results_dict[i])

        emit_progress("Complete", 100)
        emit_log(f"Finished! Fast-scraped {len(jobs)} jobs and generated {len(messages)} tailored referral pitches.")
        return messages
