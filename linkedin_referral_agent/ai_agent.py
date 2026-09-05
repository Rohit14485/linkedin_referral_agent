"""
AI Pitch Agent Module.
Crafts tailored referral and outreach messages customized for Recruiters vs. Hiring Managers.
Supports OpenAI / Gemini compatible endpoints with an intelligent heuristic fallback.
"""

import json
import logging
from typing import Optional, Tuple
from .models import CandidateProfile, ContactPerson, ContactRole, JobPosting, OutreachMessage, OutreachStatus

logger = logging.getLogger(__name__)


class OutreachAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")

    def craft_outreach(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        contact: ContactPerson
    ) -> OutreachMessage:
        """
        Generates a personalized subject and body for a candidate, job, and contact.
        """
        if self.client:
            try:
                subject, body = self._generate_with_llm(candidate, job, contact)
                return OutreachMessage(
                    recipient=contact,
                    job=job,
                    subject=subject,
                    body=body,
                    status=OutreachStatus.DRAFT
                )
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}. Using intelligent fallback generator.")

        subject, body = self._generate_heuristic(candidate, job, contact)
        return OutreachMessage(
            recipient=contact,
            job=job,
            subject=subject,
            body=body,
            status=OutreachStatus.DRAFT
        )

    def _generate_with_llm(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        contact: ContactPerson
    ) -> Tuple[str, str]:
        role_instructions = (
            "The recipient is a Technical Recruiter/HR. Focus on clear credentials, specific Job ID, "
            "matching tech stack, and clear availability. Be courteous, concise, and recruiter-friendly."
            if contact.role_category == ContactRole.RECRUITER
            else
            "The recipient is an Engineering Manager / Hiring Lead. Focus on architectural impact, technical "
            "synergy with the team's mission, and concrete project outcomes. Be concise, technical, and respectful of their time."
        )

        prompt = f"""
You are an expert career agent crafting a concise, highly converting referral request email.

{role_instructions}

[CANDIDATE INFORMATION]
- Name: {candidate.full_name}
- Years of Experience: {candidate.years_of_experience}
- Summary: {candidate.summary}
- Skills: {', '.join(candidate.key_skills)}
- LinkedIn: {candidate.linkedin_url}

[TARGET JOB]
- Title: {job.title}
- Company: {job.company_name}
- Job ID: {job.job_id}
- URL: {job.job_url}
- Description: {job.description}

[RECIPIENT]
- Name: {contact.first_name} {contact.last_name}
- Title: {contact.role_title}
- Role Category: {contact.role_category.value}

Write an email that:
1. Greets {contact.first_name} warmly and professionally.
2. Mentions the exact role ({job.title}) and why {job.company_name} stands out.
3. Highlights 2-3 specific technical synergies from the candidate's background.
4. Asks politely if they would be open to submitting an internal referral or reviewing the attached resume.
5. Keeps the entire message under 160 words.

Return strictly a valid JSON object in this format:
{{
  "subject": "Email Subject Line",
  "body": "Email body message with newlines"
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You craft high-converting, courteous professional referral emails. Always respond with JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        data = json.loads(response.choices[0].message.content)
        return data.get("subject", f"Referral Request: {job.title}"), data.get("body", "")

    def _generate_heuristic(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        contact: ContactPerson
    ) -> Tuple[str, str]:
        """
        Intelligent rule-based personalization template engine.
        """
        skills_str = ", ".join(candidate.key_skills[:3]) if candidate.key_skills else "distributed systems and software development"

        if contact.role_category == ContactRole.RECRUITER:
            subject = f"Candidate Inquiry: {job.title} (Req #{job.job_id}) - {candidate.full_name}"
            body = (
                f"Hi {contact.first_name},\n\n"
                f"I noticed {job.company_name} is currently recruiting for the {job.title} role (Req #{job.job_id}), "
                f"and I wanted to reach out directly given your focus on talent at {job.company_name}.\n\n"
                f"With {candidate.years_of_experience}+ years of software engineering experience specializing in {skills_str}, "
                f"I have successfully delivered scalable production systems that align closely with what this role entails. {candidate.summary}\n\n"
                f"I have attached my resume for your review. Would you be open to a brief conversation, or forwarding my profile "
                f"to the hiring team for consideration?\n\n"
                f"Thank you for your time and guidance!\n\n"
                f"Best regards,\n"
                f"{candidate.full_name}\n"
                f"{candidate.linkedin_url or candidate.email}"
            )
        else:
            # Hiring Manager / Engineering Lead
            subject = f"Connecting re: {job.title} & engineering at {job.company_name}"
            body = (
                f"Hi {contact.first_name},\n\n"
                f"I hope you're having a productive week. I've been following {job.company_name}'s recent work, "
                f"and saw that your team is expanding with an opening for a {job.title}.\n\n"
                f"Given your role leading {contact.role_title}, I wanted to touch base directly. My background includes "
                f"{candidate.years_of_experience}+ years engineering robust backend and distributed architectures, with strong proficiency in {skills_str}. "
                f"{candidate.summary}\n\n"
                f"I've attached my resume and would be grateful if you might consider me for an internal referral, or point me toward the right team lead.\n\n"
                f"Appreciate your time,\n"
                f"{candidate.full_name}\n"
                f"{candidate.linkedin_url or candidate.email}"
            )

        return subject, body
