# AUTOMATED CANDIDATE REVIEW SYSTEM

## Standard Operating Procedure & Executive Briefing

| Field | Detail |
|---|---|
| **Document Title** | Automated Candidate Review System (ACRS) |
| **SOP Number** | SOP-HR-001 |
| **Department** | Human Resources / Talent Acquisition |
| **Effective Date** | February 16, 2026 |
| **Version** | 3.2 |
| **Prepared By** | HR Operations |
| **Approved By** | _______________________________ |
| **Classification** | INTERNAL USE ONLY |

---

## 1.0 Executive Summary

The Automated Candidate Review System (ACRS) is an integrated suite of workflows that handles resume evaluation, candidate communication, and applicant data management for all incoming Paycor applications. The system operates continuously, processing each new application within minutes of submission.

When a candidate applies, ACRS performs three functions automatically. First, it generates a **Talent Intelligence Report (TIR)** — a scored evaluation with strengths, concerns, and recommended next steps — and delivers it to the hiring manager's inbox. Second, it sends the candidate a personalized acknowledgment email that references specific details from their resume and includes targeted follow-up questions. Third, it indexes the resume into a searchable database accessible through a **Microsoft Teams AI chatbot**, allowing hiring managers to query the full applicant pool in natural language at any time.

The hiring manager's workflow centers on reviewing evaluations, researching candidates through the AI agent, and making contact decisions — supported at each step by structured data rather than raw resumes. All candidate information, evaluation results, and processing history are logged automatically to a centralized Excel workbook for reporting and export.

---

## 2.0 System Architecture

### How the System Works

The ACRS operates as three independent automated workflows that activate together whenever a new application is submitted through Paycor. No manual trigger is required.

> **[VISUAL: ACRS System Architecture Flow]**
>
> *Gamma prompt:* A flat corporate infographic showing a system architecture with three parallel workflows. At the top, a single entry point labeled "Candidate Applies via Paycor" with a downward arrow labeled "Polled every 15 minutes" that splits into three branches. The three branches lead to three equal workflow cards arranged side by side: Workflow 1 "Candidate Evaluation Pipeline" with an envelope icon (reads resume, AI scores candidate, generates report, emails hiring manager, acknowledges candidate), Workflow 2 "Resume Indexing Service" with a database icon (converts resume to searchable data, indexes in database, logs to processing spreadsheet), and Workflow 3 "HR AI Agent" with a chat bubble icon (accepts plain-English Teams queries, searches applicant pool, returns ranked results). Below all three cards, a footer row shows hiring manager touchpoints for each workflow. Style: clean minimal diagram with a dark navy corporate palette, muted teal and blue accents for each workflow branch, and white text on dark cards. Professional and strictly informational, no decorative elements.
>
> *Gamma settings:* Style: Corporate / Clean | Enhance: Yes
>
> *Manual note:* Verify all three workflow cards are legible and evenly spaced; adjust card labels if text is truncated.

### System Overview Table

| Workflow | Trigger | What It Does | Your Role |
|---|---|---|---|
| **Candidate Evaluation Pipeline** | Every 15 min (automatic) | Pulls new applications from Paycor, AI-evaluates each resume, generates and delivers TIR to hiring manager, sends personalized acknowledgment email to candidate | Review TIR when it arrives |
| **Resume Indexing Service** | Every 15 min (automatic) | Converts resumes into structured searchable data; logs all candidate information to the Candidate Processing Log; powers the HR AI Agent | None — fully automatic |
| **HR AI Agent** | On-demand (Teams DM) | Accepts natural language questions, searches all indexed candidates, returns scored assessments with conversation memory | Ask questions whenever you need insight |

---

## 3.0 Key Terms

| Term | Definition |
|---|---|
| **Talent Intelligence Report (TIR)** | The evaluation email delivered for each new applicant — a scored assessment with strengths, concerns, risk/opportunity ratings, and recommended next steps. |
| **HR AI Agent** | The Microsoft Teams chatbot that searches the full candidate database and returns comparative insights on demand. Maintains conversation context within a session. |
| **Candidate Acknowledgment Email** | The automated, personalized email each applicant receives within minutes of applying, referencing specific resume details and including targeted follow-up questions. |
| **Candidate Processing Log** | The Excel workbook in the HR Agent OneDrive containing all processed candidate data, AI evaluation results, and application metadata. |
| **ACRS** | Automated Candidate Review System — the collective name for all three workflows described in this document. |

---

## 4.0 Your Workflow: Step by Step

> **[VISUAL: Hiring Manager Workflow Timeline]**
>
> *Gamma prompt:* A horizontal five-step timeline strip showing a hiring manager's daily workflow through the candidate review system. The five steps flow left to right, each with a simple icon above and a label below: (1) Get Notified — envelope icon — "TIR arrives in your inbox," (2) Review TIR — clipboard icon — "Read the scored evaluation," (3) Research — chat bubble icon — "Ask the AI Agent questions," (4) Decide — fork/branch icon — "Reach out, wait, or pass," (5) Interview Prep — checklist icon — "Build questions from TIR insights." Between steps 1 and 2, annotate "under 20 minutes from application." The connection between steps 2 and 3 should appear dashed or lighter to indicate the research step is optional. Style: clean minimal corporate timeline on a light background with dark navy connecting line and teal-to-blue accent circles for each milestone. Professional executive tone, no playful or cartoon elements.
>
> *Gamma settings:* Style: Minimal / Professional | Enhance: Yes
>
> *Manual note:* Confirm the dashed line between steps 2-3 renders correctly to indicate the optional step; verify all five labels are readable.

This section is your daily operating guide. Each step below maps to an action you take as a hiring manager using the ACRS.

### 4.1 Get Notified

You want to see new evaluations the moment they arrive — not discover them buried in your inbox hours later.

**Set up an Outlook inbox rule:**

1. Open Outlook and navigate to **Rules** (Settings > Mail > Rules).
2. Create a new rule with these conditions:
   - **Subject contains:** "Candidate Evaluation"
   - **Actions:** Flag for follow-up, assign a category (e.g., "ACRS - New Candidate"), and enable desktop or mobile notifications.
3. Save the rule and verify it catches the next incoming TIR.

**Alternative:** Add a Focused Inbox override so TIR emails always land in your primary tab, not "Other."

Why this matters: The system delivers evaluations within 20 minutes of an application. Your notification setup determines whether you act on that speed advantage or lose it to inbox clutter.

### 4.2 Review the Talent Intelligence Report

Each TIR is structured for a fast, confident read. Target: review within **one business day** of receipt.

**What you will find in the report:**

| Section | What to Look For |
|---|---|
| **Executive Summary** | Overall score (1-10), risk level, opportunity level — your at-a-glance verdict |
| **Candidate Profile** | Name, contact info, current title, years of experience, key skills |
| **Position Details** | Role applied for, department, location, pay range, remote eligibility |
| **Strengths** (green) / **Concerns** (red) | Side-by-side comparison for quick trade-off analysis |
| **Risk Assessment** (red) | Potential hiring risks with supporting explanation |
| **Opportunity Assessment** (green) | Growth potential indicators with supporting explanation |
| **Score Justification** | The reasoning behind the numerical rating — read this if the score surprises you |
| **Recommended Next Steps** | AI-suggested course of action based on the full evaluation |
| **AI Adoption Assessment** | Candidate readiness for modern tools and automation |

> **[VISUAL: TIR Email Report Preview]**
>
> *Gamma prompt:* A flat corporate infographic titled "Anatomy of a Talent Intelligence Report" showing the sections of the report as stacked content blocks flowing from top to bottom. At the top, a dark navy banner labeled "TALENT INTELLIGENCE REPORT." Directly below, a prominent score circle showing "7.8 / 10" with small badges for "Risk: Low" and "Opportunity: High" beside it. Then flowing downward through labeled sections: Candidate Profile (name, contact, skills), a side-by-side split of Strengths (with a green accent) and Concerns (with a red accent), Risk Assessment (soft red background tint), Opportunity Assessment (soft green background tint), Score Justification, and finally a call-to-action button labeled "Email Candidate" at the bottom. Style: clean minimal wireframe infographic with a professional executive palette — dark navy header, muted teal accents, soft green and red section highlights. The visual should communicate the report structure and reading flow, not simulate a screenshot. Each section should be clearly labeled and visually distinct.
>
> *Gamma settings:* Style: Corporate / Infographic | Enhance: Yes
>
> *Manual note:* Verify the Strengths/Concerns side-by-side layout renders as two columns, not stacked; confirm the score circle is prominent at the top.

**If the report header says "INCOMPLETE DATA":** The AI evaluated the candidate with limited information. Check the missing-fields notation and factor those gaps into your assessment — incomplete data does not mean an unqualified candidate. Consider requesting the full resume directly.

### 4.3 Research the Candidate (Teams AI Agent)

The HR AI Agent is useful before contacting a candidate, when comparing applicants across roles, or when searching for talent for a position you have not posted yet. Use it at any point in your workflow.

**How to use it:**

1. Open **Microsoft Teams** and find the **HR AI Agent** in your direct messages.
2. Type your question in plain English. The agent understands natural language — no special syntax required.
3. Read the response. The agent returns a **Talent Pool Assessment** with strongest matches, key differentiators, and suggestions for refining your search.
4. Ask follow-up questions. The agent retains conversation context for the duration of your session, so you can drill down without repeating yourself.

**Example queries:**

| What You Want to Know | What to Type |
|---|---|
| Deep dive on one person | "What can you tell me about [Candidate Name]?" |
| Head-to-head comparison | "How does [Candidate A] compare to [Candidate B] for the warehouse lead role?" |
| Skill-based search | "Who in the applicant pool has experience with supply chain management?" |
| Score-based filtering | "Which recent applicants scored above 7?" |
| Role exploration | "Who would be a strong fit for a customer service manager position?" |

### 4.4 Decide Your Next Move

After reviewing the TIR and (optionally) consulting the AI Agent, you have three paths:

**Option A — Reach out now.** At the bottom of each TIR, there is a blue **"Email [Candidate Name]"** button. Click it to open a pre-addressed email draft with the candidate's address, a subject line referencing the position, and a greeting. Write your message using what you learned from the TIR and any AI Agent research, then send. This is the fastest path from evaluation to direct engagement.

**Option B — Wait for the candidate's reply.** The candidate has already received a personalized acknowledgment email with follow-up questions about gaps in their application. If you want more information before committing to outreach, give them time to respond. Their answers often clarify what the resume did not cover — employment gaps, certifications in progress, relocation willingness.

**Option C — Pass.** If the candidate is not a fit, no action is needed. They have already been acknowledged professionally with a personalized email. Their data remains in the searchable database and may surface later for a different role.

### 4.5 Prepare for the Interview

Once you have decided to interview a candidate, consolidate your preparation:

1. **Re-read the TIR** — focus on the score, strengths, concerns, and risk factors. These are your interview anchors.
2. **Check for a candidate reply** to the acknowledgment email's follow-up questions. Their answers often surface details the resume did not cover.
3. **Query the HR AI Agent** for comparative context: "How does this candidate stack up against others who applied for [Role]?" This gives you calibration — you will know whether you are looking at a top-tier applicant or a middle-of-the-pack candidate.
4. **Build interview questions** directly from the TIR's **Areas of Concern** and **Risk Assessment** sections. These highlight exactly where to probe. The AI has already identified the unknowns — your interview resolves them.

### 4.6 Access Raw Data and Exports

All processed candidate data is automatically recorded in the **Candidate Processing Log** — an Excel workbook titled **AUTO PAY PLUS CANDIDATE PROCESSING LOG** in the **HR Agent OneDrive**.

**What the log contains:** Candidate identifiers, contact information, application metadata (source, date, pipeline stage, status, location), AI evaluation results (score, strengths, weaknesses, risk, opportunity, AI adoption readiness), job details (title, department, pay range), and processing timestamps.

**To export data:**

1. Open the workbook in Excel or Excel Online.
2. Apply filters to isolate specific roles, date ranges, or score thresholds.
3. Export in your preferred format — CSV, PDF, or XLSX.

> **Important:** The log updates automatically every time a candidate is processed. Do not make manual edits — they will be overwritten on the next processing cycle. For BI tool integration or bulk analysis, export to CSV first.

---

## 5.0 Business Impact

### Speed to Engagement

The ACRS processes every application within 15 minutes of submission and delivers both the hiring manager evaluation and the candidate acknowledgment email within 20 minutes. The industry standard for initial candidate contact ranges from 2-7 business days. This system compresses that timeline to minutes.

### 100% Acknowledgment Rate

Every candidate who applies receives a personalized response — not a generic "we received your application" template, but an email that references specific details from their resume and asks relevant follow-up questions. No candidate falls through the cracks regardless of application volume, hiring manager availability, or time of submission.

### Standardized Evaluation

Every applicant is scored on the same criteria by the same AI model. This eliminates evaluation inconsistency across hiring managers, removes the risk of unconscious bias in initial screening, and creates a defensible, auditable record of how each candidate was assessed.

### Searchable Talent Pool

Every resume processed by the system is indexed and searchable through the Teams AI Agent. Candidates who were not a fit for one role may be ideal for a future opening. The database grows with every application and retains value indefinitely — the system builds institutional knowledge automatically.

### Time Reclaimed

The manual tasks the system automates — reading resumes, forming initial evaluations, drafting acknowledgment emails, logging candidate data, and organizing applicant information — represent 20-45 minutes of hiring manager time per candidate. For a role that generates 30 applications, that is 10-22 hours of manual work eliminated per open position.

---

## 6.0 Roles and Responsibilities

| Role | Responsibility |
|---|---|
| **Hiring Manager** | Set up email notifications; review TIRs within one business day; query the HR AI Agent for research and comparisons; contact candidates using the TIR email button; use system data for interview preparation; export data from the Candidate Processing Log as needed. |
| **HR Administrator** | Monitor system health and processing metrics; manage the Paycor integration; train hiring managers on this SOP; manage OneDrive access permissions; review acknowledgment email quality periodically. |
| **IT Operations** | Maintain workflow infrastructure (n8n, database, integrations); manage credentials and API connections; respond to escalated technical issues; monitor system response times. |

---

## 7.0 System Response Times

| Event | Expected Time |
|---|---|
| New Paycor application detected | Within 15 minutes of submission |
| TIR delivered to hiring manager | Within 20 minutes of detection |
| Candidate acknowledgment email sent | Within 20 minutes of detection |
| Resume indexed in search database | Within 30 minutes of detection |
| HR AI Agent query response | Immediate (under 30 seconds) |

---

## 8.0 Troubleshooting

| Issue | What to Do |
|---|---|
| TIR not received | Confirm the application exists in Paycor. Check your spam/junk folder and Outlook "Other" tab. If both look fine, contact IT Operations. |
| TIR shows "INCOMPLETE DATA" | The AI evaluated with limited information. Review what is available and consider requesting the full resume from the candidate directly. This does not indicate a system error. |
| HR AI Agent not responding | Check your Teams connection and internet status. Confirm the bot appears in your DM list. If it is still unresponsive, contact IT Operations. |
| "Email Candidate" button not working | Copy the email address from the Candidate Profile section of the TIR and compose your email manually. Report the button issue to IT Operations. |
| Candidate did not receive acknowledgment email | Verify the email address in Paycor is correct and does not contain typos. Contact IT Operations to review the execution logs for that candidate. |
| Candidate Processing Log appears outdated | The log updates on each processing cycle (every 15 minutes). If data is missing after 30 minutes, contact IT Operations. Do not attempt manual corrections. |

---

## 9.0 Document Control

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-02-15 | Initial release. |
| 1.2 | 2026-02-15 | Condensed to 4-page format. Added email notification setup, data export procedures, Candidate Processing Log reference. |
| 2.0 | 2026-02-16 | Rewritten for executive readability and entry-level accessibility. Added narrative overview. Converted to active voice throughout. |
| 3.0 | 2026-02-16 | Expanded to executive hybrid format. Added Executive Summary, Business Impact section, and system architecture visual. Restructured as combined executive report and operational guide. |
| 3.1 | 2026-02-16 | Replaced ASCII diagram with visual design prompts. Added TIR preview and workflow timeline visual prompts. |
| 3.2 | 2026-02-16 | Optimized visual prompts for Gamma.app AI image generator. Replaced technical specs with SPLICE-framework descriptive prompts. |

---

*INTERNAL USE ONLY — AutoPayPlus. Unauthorized distribution prohibited.*

--- END OF DOCUMENT ---
