"""
Data models for LinkedIn Referral & Outreach AI Agent.
"""

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ContactRole(str, Enum):
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    PEER_ENGINEER = "peer_engineer"
    EXECUTIVE = "executive"
    OTHER = "other"


class VerificationSource(str, Enum):
    PATTERN_GUESS = "PATTERN_GUESS"    # Synthesized from company domain pattern (Unverified)
    API_VERIFIED = "API_VERIFIED"      # Enriched from Hunter.io / Apollo API
    SERPER_OSINT = "SERPER_OSINT"      # Derived from Serper.dev Google search
    MANUAL = "MANUAL"                  # Manually provided/confirmed by user


class JobPosting(BaseModel):
    job_id: str = Field(..., description="Unique LinkedIn or external Job ID")
    title: str = Field(..., description="Job title, e.g., AI Engineer")
    company_name: str = Field(..., description="Name of hiring organization")
    company_domain: Optional[str] = Field(None, description="Domain name, e.g., stripe.com")
    location: str = Field("India", description="Job location or Remote status")
    job_url: str = Field(..., description="Direct link to job listing")
    description: Optional[str] = Field("", description="Job description or requirements summary")
    posted_date: Optional[str] = Field("", description="Posting time, e.g., 2 days ago")
    posted_datetime: Optional[str] = Field("", description="ISO date, e.g., 2026-09-03")

    @field_validator("company_domain", mode="before")
    @classmethod
    def clean_domain(cls, v):
        if not v:
            return None
        v = str(v).lower().strip()
        v = v.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        return v


class ContactPerson(BaseModel):
    first_name: str
    last_name: str
    role_title: str
    role_category: ContactRole = ContactRole.RECRUITER
    email: str
    company_name: str
    company_domain: Optional[str] = None
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    linkedin_url: Optional[str] = None
    verification_source: VerificationSource = VerificationSource.PATTERN_GUESS
    email_candidates: List[str] = Field(default_factory=list)

    def model_post_init(self, __context):
        if not self.email_candidates and self.first_name:
            clean_co = re.sub(r"[^a-zA-Z0-9]", "", self.company_name).lower() if self.company_name else "company"
            domain = self.company_domain or f"{clean_co}.com"
            self.email_candidates = self.generate_permutations(self.first_name, self.last_name, domain, self.email)

    @staticmethod
    def generate_permutations(first: str, last: str, domain: str, primary_email: str = "") -> List[str]:
        f = first.lower().strip()
        l = last.lower().strip() if last else ""
        d = domain.lower().strip()
        
        patterns = []
        if primary_email:
            patterns.append(primary_email)
            
        if f and l and f not in ["hiring", "talent", "hr"]:
            f_initial = f[0]
            l_initial = l[0]
            patterns.extend([
                f"{f}.{l}@{d}",
                f"{f}{l}@{d}",
                f"{f_initial}{l}@{d}",
                f"{f_initial}.{l}@{d}",
                f"{f}{l_initial}@{d}",
                f"{f}.{l_initial}@{d}",
                f"{f}_{l}@{d}",
                f"{l}.{f}@{d}",
                f"{l}{f}@{d}",
                f"{f}@{d}",
            ])
            # Include numbered patterns up to 30 for duplicate names at large companies
            for i in range(1, 31):
                patterns.append(f"{f}.{l}{i}@{d}")
                patterns.append(f"{f}{i}@{d}")
                patterns.append(f"{f_initial}{l}{i}@{d}")
        else:
            patterns.extend([
                f"recruiting@{d}",
                f"careers@{d}",
                f"hr@{d}",
                f"talent@{d}"
            ])
            for i in range(1, 31):
                patterns.append(f"{f}{i}@{d}")

        seen = set()
        unique = []
        for p in patterns:
            if p and p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class CandidateProfile(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    github_url: Optional[str] = ""
    portfolio_url: Optional[str] = ""
    summary: str = Field(..., description="Short professional summary of background and achievements")
    key_skills: List[str] = Field(default_factory=list)
    years_of_experience: int = Field(0, ge=0)
    resume_path: Optional[str] = None


class OutreachStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class OutreachMessage(BaseModel):
    recipient: ContactPerson
    job: JobPosting
    subject: str
    body: str
    status: OutreachStatus = OutreachStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
