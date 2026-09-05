# LinkedIn Referral & Outreach AI Agent

An automated, ethical career outreach suite that identifies target job postings, locates HR recruiters and engineering hiring managers, generates personalized referral pitches using AI, and manages dispatch via safe Dry-Run or live SMTP.

---

## Features

- 🔎 **Job Discovery**: Discovers openings using LinkedIn's public guest job search, with offline seed fallback for resilience.
- 👥 **Role-Aware Contact Finder**: Automatically categorizes target contacts into **HR / Talent Acquisition** and **Hiring Managers / Engineering Leads**.
- 🧠 **AI-Powered Personalization**: Analyzes the candidate's resume, specific Job ID, and recipient's role to craft distinct, high-converting messages.
- 🛡️ **Safe Dry-Run by Default**: Saves all generated emails (`.eml` and metadata `.json`) to `./outbox/` with resume attachments before touching live mail servers.
- 🖥️ **Interactive Terminal Dashboard**: Preview cards, edit drafts on the fly, approve, or skip with single-key actions.

---

## Quick Start

### 1. Installation

```bash
cd /Users/rohitrajgupta/.gemini/antigravity/scratch/linkedin_referral_agent
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your desired settings:

```bash
cp .env.example .env
```

Key configuration options:
- `DRY_RUN=true` (Keep `true` for previewing drafts in `./outbox/`)
- `OPENAI_API_KEY`: (Optional) Connects to OpenAI or Gemini OpenAI-compatible endpoints for frontier LLM copy.
- `SMTP_USER` & `SMTP_PASSWORD`: (Optional) Gmail App Password or SMTP credentials for live sending.

### 3. Run the CLI

Interactive Mode (Prompt for every draft):
```bash
python3 -m linkedin_referral_agent.cli --role "Backend Engineer" --location "Remote"
```

Batch / Auto-Approve Dry-Run:
```bash
python3 -m linkedin_referral_agent.cli --role "Platform Engineer" --auto-approve
```

Custom Resume & Count:
```bash
python3 -m linkedin_referral_agent.cli --role "Machine Learning" --resume "sample_data/sample_resume.txt" --max-jobs 3 --contacts-per-job 2
```

---

## Running Automated Tests

Run the full unit and integration test suite:

```bash
python3 -m pytest tests/ -v
```
