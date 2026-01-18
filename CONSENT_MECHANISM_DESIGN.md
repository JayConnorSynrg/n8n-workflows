# Consent Mechanism Design Document
## Multi-Jurisdiction Consent Collection for Voice Agent System

**Document Version:** 1.0
**Date:** January 17, 2026
**Author:** ConsentMechanismAgent
**System:** Teams Voice Bot with Recall.ai, Deepgram, Groq, Cartesia, n8n
**Jurisdictions:** EU/EEA (GDPR), UK (UK GDPR), California (CCPA/CPRA), US Multi-State

---

## Executive Summary

This document provides a comprehensive consent collection system design for a voice agent that processes biometric data (voice recordings) across multiple jurisdictions. The system satisfies:

- **GDPR Article 9**: Explicit consent for biometric data processing
- **UK GDPR**: ICO-specific guidance on voice recordings
- **CCPA/CPRA**: Notice at collection and sensitive personal information consent
- **Two-Party Consent States**: All-party recording consent requirements

### Critical Design Principles

1. **Consent MUST be explicit** - No pre-ticked boxes, no implied consent
2. **Consent MUST be granular** - Separate opt-ins for each processing purpose
3. **Consent MUST be withdrawable** - Real-time and post-meeting withdrawal options
4. **Consent MUST be documented** - Immutable audit trail for accountability
5. **Consent MUST be jurisdiction-aware** - Different requirements for EU/UK/US users

---

## 1. Consent Flow Architecture

### 1.1 Consent Collection Entry Points

```
┌─────────────────────────────────────────────────────────────┐
│                    CONSENT ENTRY POINTS                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. PRE-MEETING CONSENT (Host - Meeting Scheduler)           │
│     ├─ Host enables voice bot for meeting                    │
│     ├─ Host reviews participant consent requirements         │
│     ├─ Host sends pre-meeting consent email to participants  │
│     └─ Participants opt-in before meeting starts             │
│                                                               │
│  2. IN-MEETING CONSENT (Participants - Meeting Join)         │
│     ├─ Bot joins meeting and announces itself                │
│     ├─ Bot presents consent banner/notification              │
│     ├─ Participants opt-in via Teams chat or voice           │
│     └─ Recording paused until all participants consent       │
│                                                               │
│  3. MID-MEETING CONSENT (Late Joiners)                       │
│     ├─ Bot detects new participant joining                   │
│     ├─ Bot announces recording to new participant            │
│     ├─ Bot requests consent from new participant             │
│     └─ Participant opts in or meeting pauses for them        │
│                                                               │
│  4. POST-MEETING CONSENT WITHDRAWAL                          │
│     ├─ Participant receives meeting summary email            │
│     ├─ Email contains "Withdraw Consent" link                │
│     ├─ Participant can request data deletion                 │
│     └─ System deletes participant's data within 72 hours     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Consent Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│                  CONSENT DECISION FLOW                       │
└─────────────────────────────────────────────────────────────┘

START: Bot receives meeting invitation
   │
   ├─> Is participant in EU/EEA or UK?
   │    │
   │    YES ──> GDPR/UK GDPR Flow (Explicit Consent Required)
   │    │       │
   │    │       ├─> Pre-meeting email with consent form
   │    │       ├─> In-meeting banner with granular options
   │    │       ├─> MUST consent to biometric processing
   │    │       └─> Bot does NOT record until consent given
   │    │
   │    NO ──> Is participant in California?
   │             │
   │             YES ──> CCPA/CPRA Flow
   │             │       │
   │             │       ├─> Notice at collection required
   │             │       ├─> Opt-out option for sale/sharing
   │             │       ├─> "Do Not Sell My Info" link
   │             │       └─> Consent to sensitive PI processing
   │             │
   │             NO ──> Is participant in two-party consent state?
   │                      │
   │                      YES ──> All-Party Consent Flow
   │                      │       │
   │                      │       ├─> Bot announces recording
   │                      │       ├─> ALL participants must consent
   │                      │       ├─> One objection = no recording
   │                      │       └─> Criminal liability if violated
   │                      │
   │                      NO ──> Default US Flow (One-Party Consent)
   │                               │
   │                               ├─> Host consent sufficient
   │                               ├─> Notice to participants (best practice)
   │                               └─> Recording proceeds
```

---

## 2. Consent UI/UX Designs (Text-Based Mockups)

### 2.1 Pre-Meeting Consent Email (GDPR/UK GDPR)

**Subject:** [MEETING HOST NAME] has invited a Voice AI Assistant to your meeting - Consent Required

**Email Body:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                 VOICE AI ASSISTANT CONSENT REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hello [PARTICIPANT NAME],

[HOST NAME] has invited a Voice AI Assistant to your upcoming meeting:

    📅 Meeting: [MEETING TITLE]
    🕒 Date/Time: [DATE/TIME]
    👤 Host: [HOST NAME]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    YOUR CONSENT IS REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before the Voice AI Assistant can join this meeting, we need your
explicit consent to process your personal data, including voice
recordings (which are considered biometric data under GDPR).

⚠️ IMPORTANT: The Voice AI Assistant will NOT join the meeting or
record any audio unless ALL participants provide consent below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                 WHAT DATA WILL BE PROCESSED?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Voice AI Assistant will process the following data:

✓ Voice recordings (biometric data - GDPR Article 9)
✓ Speech transcriptions
✓ Your name and email address
✓ Meeting metadata (date, time, participants)
✓ Tool actions requested during the meeting

This data will be shared with the following third parties:
  • Recall.ai (meeting recording)
  • Deepgram (speech-to-text transcription)
  • Groq (AI language model)
  • Cartesia (text-to-speech synthesis)
  • Supabase (secure data storage - EU region)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                   HOW WILL DATA BE USED?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your data will be used for the following purposes:

1. MEETING ASSISTANCE (Required for core functionality)
   - Real-time transcription of conversations
   - Executing actions requested during the meeting
     (e.g., sending emails, scheduling meetings)
   - Generating meeting summaries

2. SERVICE IMPROVEMENT (Optional - you can opt out)
   - Quality metrics (transcription accuracy, audio quality)
   - Usage analytics (feature usage, session duration)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                   DATA RETENTION PERIOD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your data will be retained for the following periods:

  • Voice recordings: Deleted immediately after transcription
  • Transcripts: 90 days after meeting
  • Tool execution logs: 90 days after meeting
  • Meeting summaries: 1 year after meeting

You can request deletion of your data at any time (see below).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      YOUR RIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Under GDPR, you have the following rights:

✓ Right of access (view your data)
✓ Right to rectification (correct errors)
✓ Right to erasure ("right to be forgotten")
✓ Right to restrict processing
✓ Right to data portability
✓ Right to object to processing
✓ Right to withdraw consent at any time

To exercise your rights, contact: privacy@synrgscaling.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              PLEASE PROVIDE YOUR CONSENT BELOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please select your consent preferences:

┌────────────────────────────────────────────────────────────┐
│ [ ] I consent to the Voice AI Assistant recording and     │
│     processing my voice (biometric data) for the purposes  │
│     described above. (REQUIRED)                            │
│                                                             │
│ [ ] I consent to my data being used for service            │
│     improvement and analytics. (OPTIONAL)                  │
│                                                             │
│ [ ] I consent to receiving meeting summaries via email.    │
│     (OPTIONAL)                                              │
└────────────────────────────────────────────────────────────┘

           [ SUBMIT CONSENT ]    [ DECLINE ]

By clicking "Submit Consent," you acknowledge that you have read
and understood the Privacy Notice and consent to the processing
of your personal data as described above.

You can withdraw your consent at any time by clicking the
"Withdraw Consent" link in any meeting summary email or by
contacting privacy@synrgscaling.com.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      PRIVACY NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Data Controller: SYNRG Scaling LLC
                 [ADDRESS]
                 privacy@synrgscaling.com

Privacy Notice: https://synrgscaling.com/voice-ai-privacy
Terms of Service: https://synrgscaling.com/voice-ai-terms

Questions? Contact our Data Protection Officer:
  dpo@synrgscaling.com
  +1 [PHONE NUMBER]

Supervisory Authority (EU): Your local data protection authority
  Find yours: https://edpb.europa.eu/about-edpb/board/members_en

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Technical Implementation:**
- Email sent via n8n Gmail node
- Consent form hosted on secure HTTPS page
- Unique consent token embedded in URL
- Consent response stored in `participant_consent` table

---

### 2.2 In-Meeting Bot Announcement (Teams Chat)

**Teams Chat Message (Bot sends on join):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                 🤖 VOICE AI ASSISTANT HAS JOINED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hello! I'm the Voice AI Assistant invited by [HOST NAME].

⚠️ RECORDING CONSENT REQUIRED ⚠️

I can help with:
  • Taking meeting notes and summaries
  • Sending emails and scheduling meetings
  • Answering questions about company documents

Before I can start recording and processing your voice, I need
your explicit consent.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 RECORDING IS CURRENTLY PAUSED 🔴

To provide consent, please:

1. Review the consent form: [CONSENT LINK]
2. Click "I Consent" below, OR
3. Say "I consent to recording" out loud

   [ I CONSENT TO RECORDING ]    [ I DO NOT CONSENT ]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 What happens to my data?
   • Voice deleted immediately after transcription
   • Transcripts stored for 90 days
   • You can withdraw consent at any time

🔒 Privacy Notice: [PRIVACY LINK]
❓ Questions? Contact: privacy@synrgscaling.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Status:
  ✅ [PARTICIPANT 1] - Consented
  ⏳ [PARTICIPANT 2] - Awaiting consent
  ⏳ [PARTICIPANT 3] - Awaiting consent

Recording will begin when all participants have consented.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Audio Announcement (Bot speaks on join):**

```
"Hello, this is the Voice AI Assistant invited by [HOST NAME].

Before I can record and process your voice, I need your explicit
consent under data protection laws.

Please review the consent form in the chat, or say 'I consent to
recording' out loud.

Recording is currently paused and will begin once all participants
have provided consent."
```

---

### 2.3 Mid-Meeting Consent (Late Joiner)

**Teams Chat Message (Bot sends when new participant joins):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🔴 RECORDING IN PROGRESS - CONSENT REQUIRED 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hello [NEW PARTICIPANT NAME]!

This meeting is being recorded by the Voice AI Assistant.

⚠️ IMPORTANT: Your voice will NOT be processed or recorded until
you provide consent below.

   [ I CONSENT TO RECORDING ]    [ I DO NOT CONSENT ]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What happens if I don't consent?
  • The bot will mute you and exclude you from transcription
  • Other participants' recording will continue
  • You can still participate in the meeting manually

What happens if I consent?
  • Your voice will be transcribed and processed
  • You'll receive a meeting summary after the call
  • You can withdraw consent at any time

Privacy Notice: [PRIVACY LINK]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Audio Announcement:**

```
"Hello [NEW PARTICIPANT NAME], this meeting is being recorded
by the Voice AI Assistant.

Please provide your consent in the chat to have your voice
transcribed and processed.

If you do not consent, you will be excluded from transcription
but can still participate in the meeting."
```

---

### 2.4 Post-Meeting Consent Withdrawal Email

**Subject:** Meeting Summary: [MEETING TITLE] - Withdraw Consent Option

**Email Body:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      MEETING SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Meeting: [MEETING TITLE]
Date/Time: [DATE/TIME]
Duration: [DURATION]
Participants: [PARTICIPANT LIST]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                     KEY DISCUSSION POINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[AUTO-GENERATED SUMMARY]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                       ACTION ITEMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[AUTO-GENERATED ACTION ITEMS]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                  WITHDRAW YOUR CONSENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You provided consent for the Voice AI Assistant to record and
process your voice during this meeting.

You have the right to withdraw your consent at any time.

If you withdraw consent, we will:
  ✓ Delete your voice recordings (if not already deleted)
  ✓ Delete your transcript data
  ✓ Remove you from meeting summaries
  ✓ Delete your data from all systems within 72 hours

⚠️ Note: Withdrawing consent cannot undo actions already taken
during the meeting (e.g., emails sent, meetings scheduled).

          [ WITHDRAW CONSENT AND DELETE MY DATA ]

By clicking the button above, you confirm that you want to
withdraw your consent and have all your data from this meeting
deleted.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    MANAGE YOUR PREFERENCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View all your data: [DATA ACCESS LINK]
Download your data: [DATA EXPORT LINK]
Manage consent preferences: [PREFERENCE CENTER LINK]
Privacy Policy: [PRIVACY LINK]
Contact privacy team: privacy@synrgscaling.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 3. Consent Language Templates by Jurisdiction

### 3.1 GDPR (EU/EEA) Consent Language

**Legal Basis:** Article 6(1)(a) - Consent + Article 9(2)(a) - Explicit consent for biometric data

**Consent Text:**
```
CONSENT TO BIOMETRIC DATA PROCESSING (GDPR Article 9)

I, [PARTICIPANT NAME], hereby provide my free, specific, informed,
and unambiguous consent for SYNRG Scaling LLC to process my
personal data, including biometric data (voice recordings), for
the following purposes:

1. MEETING ASSISTANCE (Primary Purpose)
   - Recording and transcribing my voice during Microsoft Teams
     meetings
   - Processing my speech with AI models (Deepgram, Groq, Cartesia)
   - Executing actions I request during meetings (sending emails,
     scheduling meetings, querying databases)
   - Generating meeting summaries and action items

2. DATA SHARING WITH THIRD PARTIES
   I consent to my data being shared with the following third-party
   processors for the purposes described above:

   • Recall.ai (meeting recording service)
   • Deepgram (speech-to-text transcription)
   • Groq (AI language model inference)
   • Cartesia (text-to-speech synthesis)
   • Supabase (secure data storage - EU region)

   All processors are bound by Data Processing Agreements (DPAs)
   requiring GDPR compliance.

3. INTERNATIONAL DATA TRANSFERS (If applicable)
   I understand that my data may be transferred to processors
   located outside the EU/EEA, including the United States.

   These transfers are safeguarded by:
   [ ] EU-US Data Privacy Framework (for US processors)
   [ ] Standard Contractual Clauses (SCCs)
   [ ] Adequacy decisions by the European Commission

4. DATA RETENTION
   I understand that my data will be retained as follows:

   • Voice recordings: Deleted immediately after transcription
   • Transcripts: 90 days after meeting
   • Meeting summaries: 1 year after meeting
   • Tool execution logs: 90 days after meeting

5. MY RIGHTS
   I understand that I have the right to:

   ✓ Withdraw this consent at any time (without affecting prior
     processing)
   ✓ Access my personal data
   ✓ Rectify inaccurate data
   ✓ Request erasure of my data ("right to be forgotten")
   ✓ Restrict or object to processing
   ✓ Data portability
   ✓ Lodge a complaint with my supervisory authority

6. CONSEQUENCES OF REFUSING CONSENT
   I understand that if I do not provide consent, the Voice AI
   Assistant will not record or process my voice, and I will not
   be able to use the meeting assistance features.

By clicking "I CONSENT" below, I confirm that:
  • I have read and understood this consent form
  • I have had the opportunity to review the Privacy Notice
  • I freely and voluntarily provide my consent
  • I understand my right to withdraw consent at any time

┌─────────────────────────────────────────────────────────────┐
│ [ ] I CONSENT to the processing of my biometric data         │
│     (voice recordings) as described above.                    │
│                                                               │
│ Signature: ______________________  Date: __________________  │
│                                                               │
│ Email: ___________________________________________________    │
└─────────────────────────────────────────────────────────────┘

[  SUBMIT CONSENT  ]    [  DECLINE  ]

Privacy Notice: https://synrgscaling.com/voice-ai-privacy
Data Protection Officer: dpo@synrgscaling.com
Supervisory Authority: [YOUR LOCAL DPA]
```

---

### 3.2 UK GDPR Consent Language

**Legal Basis:** Article 6(1)(a) - Consent + Article 9(2)(a) - Explicit consent for biometric data

**Consent Text:**
```
CONSENT TO VOICE RECORDING AND BIOMETRIC PROCESSING (UK GDPR)

I, [PARTICIPANT NAME], provide my explicit consent for SYNRG
Scaling LLC to record and process my voice (biometric data)
during Microsoft Teams meetings.

This consent is provided in accordance with:
  • UK GDPR Article 6(1)(a) - Consent for personal data processing
  • UK GDPR Article 9(2)(a) - Explicit consent for special category
    data (biometric data)
  • ICO Guidance on voice recordings and biometric data

WHAT DATA WILL BE PROCESSED?
  • Voice recordings (biometric data)
  • Speech transcriptions
  • Meeting metadata (date, time, participants)
  • Actions requested during meetings

HOW WILL MY DATA BE USED?
  • Real-time transcription and meeting assistance
  • Executing actions requested during meetings
  • Generating meeting summaries
  • Service improvement and quality metrics (optional)

WHO WILL ACCESS MY DATA?
Your data will be shared with the following third-party processors:
  • Recall.ai (UK/US) - Meeting recording
  • Deepgram (US) - Speech-to-text
  • Groq (US) - AI processing
  • Cartesia (US) - Text-to-speech
  • Supabase (EU) - Data storage

All processors have executed Data Processing Agreements and are
committed to UK GDPR compliance.

INTERNATIONAL TRANSFERS:
Your data will be transferred to the United States for processing.
These transfers are safeguarded by:
  • UK International Data Transfer Agreement (IDTA)
  • UK-US Data Bridge (if applicable)
  • UK Addendum to EU Standard Contractual Clauses

DATA RETENTION:
  • Voice recordings: Deleted immediately after transcription
  • Transcripts: 90 days
  • Meeting summaries: 1 year

YOUR RIGHTS UNDER UK GDPR:
  ✓ Right to withdraw consent at any time
  ✓ Right of access (Subject Access Request)
  ✓ Right to rectification
  ✓ Right to erasure
  ✓ Right to restrict processing
  ✓ Right to data portability
  ✓ Right to object
  ✓ Right to lodge a complaint with the ICO

To exercise your rights, contact:
  Data Protection Officer: dpo@synrgscaling.com
  ICO (UK Supervisory Authority): https://ico.org.uk/

CONSEQUENCES OF NOT CONSENTING:
If you do not consent, the Voice AI Assistant will not record or
process your voice, and you will not be able to use meeting
assistance features.

┌─────────────────────────────────────────────────────────────┐
│ [ ] I CONSENT to the recording and processing of my voice    │
│     (biometric data) as described above.                      │
│                                                               │
│ [ ] I consent to my data being transferred to the United     │
│     States for processing (REQUIRED).                         │
│                                                               │
│ [ ] I consent to my data being used for service improvement  │
│     and analytics (OPTIONAL).                                 │
│                                                               │
│ Name: _____________________________________________________   │
│                                                               │
│ Email: ____________________________________________________   │
│                                                               │
│ Date: _____________________________________________________   │
└─────────────────────────────────────────────────────────────┘

[  SUBMIT CONSENT  ]    [  DECLINE  ]

Privacy Notice: https://synrgscaling.com/voice-ai-privacy-uk
Contact: privacy@synrgscaling.com | +44 [PHONE NUMBER]
```

---

### 3.3 CCPA/CPRA (California) Notice Language

**Legal Basis:** CCPA/CPRA Notice at Collection + Consent for Sensitive Personal Information

**Notice Text:**
```
CALIFORNIA CONSUMER PRIVACY ACT (CCPA) NOTICE AT COLLECTION

This notice is provided pursuant to the California Consumer Privacy
Act (CCPA) and California Privacy Rights Act (CPRA).

CATEGORIES OF PERSONAL INFORMATION COLLECTED:

We collect the following categories of personal information when
you use the Voice AI Assistant:

1. IDENTIFIERS
   • Name
   • Email address
   • Meeting participant ID
   • Device identifiers

2. AUDIO, ELECTRONIC, VISUAL, OR SIMILAR INFORMATION
   • Voice recordings (considered "biometric information" under
     CCPA § 1798.140(v)(1)(B) when used to identify you)
   • Speech transcriptions

3. COMMERCIAL INFORMATION
   • Meeting topics and business discussions

4. PROFESSIONAL OR EMPLOYMENT-RELATED INFORMATION
   • Job title (if shared in meeting)
   • Company affiliation

5. SENSITIVE PERSONAL INFORMATION (CPRA § 1798.140(ae))
   • Voice recordings used to identify you (biometric information)

PURPOSES FOR WHICH PERSONAL INFORMATION IS USED:

We use your personal information for the following purposes:

  • Providing the Voice AI Assistant service
  • Transcribing meeting conversations
  • Executing actions you request (sending emails, scheduling)
  • Generating meeting summaries
  • Service improvement and quality assurance
  • Detecting security incidents and preventing fraud

CATEGORIES OF THIRD PARTIES WITH WHOM WE SHARE INFORMATION:

We share your personal information with:

  • SERVICE PROVIDERS (for business purposes):
    - Recall.ai (meeting recording)
    - Deepgram (speech-to-text)
    - Groq (AI processing)
    - Cartesia (text-to-speech)
    - Supabase (data storage)

  • BUSINESS PARTNERS:
    - Meeting host and other participants (for collaboration)

WE DO NOT SELL OR SHARE YOUR PERSONAL INFORMATION.

RETENTION PERIOD:

We retain your personal information for the following periods:
  • Voice recordings: Deleted immediately after transcription
  • Transcripts: 90 days
  • Meeting summaries: 1 year

YOUR CALIFORNIA PRIVACY RIGHTS:

Under CCPA/CPRA, you have the right to:

1. KNOW what personal information we collect, use, disclose, and
   sell (if applicable)

2. DELETE your personal information (subject to exceptions)

3. CORRECT inaccurate personal information

4. OPT-OUT of the sale or sharing of your personal information
   (We do not sell or share your information)

5. LIMIT USE AND DISCLOSURE of sensitive personal information
   (voice recordings)

6. NON-DISCRIMINATION for exercising your CCPA rights

To exercise your rights, submit a verifiable consumer request to:
  • Email: privacy@synrgscaling.com
  • Phone: 1-[PHONE NUMBER]
  • Web: https://synrgscaling.com/ccpa-request

You may also designate an authorized agent to make requests on
your behalf.

CONSENT TO PROCESSING SENSITIVE PERSONAL INFORMATION:

Your voice recordings are considered "sensitive personal information"
under CPRA. We will only process your sensitive personal information
for purposes that are reasonably necessary and proportionate to
providing the Voice AI Assistant service.

┌─────────────────────────────────────────────────────────────┐
│ [ ] I consent to the collection and processing of my         │
│     sensitive personal information (voice recordings) for    │
│     the purposes described above.                            │
│                                                               │
│ [ ] I consent to receiving meeting summaries via email.      │
│     (OPTIONAL)                                                │
└─────────────────────────────────────────────────────────────┘

[  ACCEPT AND CONTINUE  ]    [  DECLINE  ]

California Privacy Notice: https://synrgscaling.com/privacy-ca
Do Not Sell My Personal Information: We do not sell your information
Contact: privacy@synrgscaling.com

EFFECTIVE DATE: [DATE]
LAST UPDATED: [DATE]
```

---

### 3.4 Two-Party Consent States (US) Notice

**States:** California, Connecticut, Florida, Illinois, Maryland, Massachusetts, Michigan, Montana, Nevada, New Hampshire, Pennsylvania, Washington

**Notice Text:**
```
NOTICE OF RECORDING - ALL-PARTY CONSENT REQUIRED

This meeting will be recorded by the Voice AI Assistant.

⚠️ IMPORTANT: Under [STATE] law, ALL participants must consent
to the recording before it can begin. Recording without all-party
consent is a criminal offense punishable by [PENALTIES].

By participating in this meeting, you acknowledge that:

1. This meeting is being recorded.

2. Your voice will be recorded, transcribed, and processed by
   AI systems.

3. The recording will be shared with the following third parties:
   • Recall.ai (recording service)
   • Deepgram (transcription service)
   • Groq (AI processing)
   • Cartesia (speech synthesis)

4. The recording will be retained for [RETENTION PERIOD].

5. You have the right to object to the recording.

CONSENT REQUIREMENT:

By clicking "I CONSENT" below, you confirm that:

  • You consent to this meeting being recorded
  • You consent to your voice being transcribed and processed
  • You understand the recording will be shared with third parties
  • You acknowledge your right to withdraw consent at any time

If you do NOT consent, please click "I DO NOT CONSENT" below.
The meeting host will be notified, and recording will not proceed
without your consent.

┌─────────────────────────────────────────────────────────────┐
│ [ ] I CONSENT to this meeting being recorded and to my       │
│     voice being transcribed and processed as described       │
│     above.                                                    │
│                                                               │
│ Name: _____________________________________________________   │
│                                                               │
│ Date: _____________________________________________________   │
│                                                               │
│ Time: _____________________________________________________   │
└─────────────────────────────────────────────────────────────┘

[  I CONSENT  ]    [  I DO NOT CONSENT  ]

⚠️ If ANY participant does not consent, recording will NOT proceed.

Privacy Policy: https://synrgscaling.com/privacy
Questions: privacy@synrgscaling.com
```

---

## 4. Database Schema for Consent Records

### 4.1 Consent Tables

```sql
-- ============================================================
-- CONSENT MANAGEMENT SCHEMA
-- ============================================================

-- Participant Consent Records (Immutable Audit Trail)
CREATE TABLE IF NOT EXISTS participant_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Participant identification
    participant_email VARCHAR(255) NOT NULL,
    participant_name VARCHAR(255),
    participant_id VARCHAR(100), -- Teams user ID

    -- Meeting context
    meeting_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    bot_id VARCHAR(100),

    -- Consent metadata
    consent_token VARCHAR(100) UNIQUE NOT NULL, -- Unique token for consent link
    consent_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        -- PENDING, GRANTED, DECLINED, WITHDRAWN, EXPIRED
    consent_method VARCHAR(50) NOT NULL,
        -- PRE_MEETING_EMAIL, IN_MEETING_CHAT, IN_MEETING_VOICE,
        -- MID_MEETING_JOIN, WEB_FORM

    -- Jurisdiction and legal basis
    jurisdiction VARCHAR(10) NOT NULL,
        -- GDPR_EU, GDPR_UK, CCPA_CA, US_TWO_PARTY, US_ONE_PARTY
    legal_basis VARCHAR(50),
        -- GDPR: "consent", "legitimate_interest"
        -- CCPA: "notice_at_collection", "sensitive_pi_consent"

    -- Granular consent options
    consent_voice_recording BOOLEAN DEFAULT FALSE,
    consent_transcription BOOLEAN DEFAULT FALSE,
    consent_ai_processing BOOLEAN DEFAULT FALSE,
    consent_analytics BOOLEAN DEFAULT FALSE,
    consent_international_transfer BOOLEAN DEFAULT FALSE,
    consent_meeting_summaries BOOLEAN DEFAULT FALSE,

    -- Consent timestamps
    consent_requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consent_granted_at TIMESTAMPTZ,
    consent_withdrawn_at TIMESTAMPTZ,
    consent_expiry_date TIMESTAMPTZ,

    -- Withdrawal metadata
    withdrawal_reason TEXT,
    withdrawal_method VARCHAR(50),
        -- EMAIL_LINK, WEB_FORM, SUPPORT_REQUEST

    -- Audit trail
    ip_address INET,
    user_agent TEXT,
    consent_version VARCHAR(20), -- Privacy policy version
    consent_text_hash VARCHAR(64), -- SHA256 of consent text shown

    -- Data retention
    data_deletion_requested BOOLEAN DEFAULT FALSE,
    data_deletion_completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_consent_status CHECK (
        consent_status IN ('PENDING', 'GRANTED', 'DECLINED', 'WITHDRAWN', 'EXPIRED')
    ),
    CONSTRAINT valid_jurisdiction CHECK (
        jurisdiction IN ('GDPR_EU', 'GDPR_UK', 'CCPA_CA', 'US_TWO_PARTY', 'US_ONE_PARTY')
    )
);

-- Indexes for consent lookups
CREATE INDEX IF NOT EXISTS idx_participant_consent_meeting
ON participant_consent(meeting_id, participant_email);

CREATE INDEX IF NOT EXISTS idx_participant_consent_token
ON participant_consent(consent_token);

CREATE INDEX IF NOT EXISTS idx_participant_consent_status
ON participant_consent(consent_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_participant_consent_email
ON participant_consent(participant_email, created_at DESC);

-- Index for withdrawal processing
CREATE INDEX IF NOT EXISTS idx_participant_consent_withdrawn
ON participant_consent(consent_status, consent_withdrawn_at)
WHERE consent_status = 'WITHDRAWN';

COMMENT ON TABLE participant_consent IS 'Immutable consent audit trail for GDPR/CCPA compliance';
COMMENT ON COLUMN participant_consent.consent_token IS 'Unique token for consent link (e.g., "cnst_abc123")';
COMMENT ON COLUMN participant_consent.jurisdiction IS 'Determines consent requirements and legal basis';
COMMENT ON COLUMN participant_consent.consent_text_hash IS 'SHA256 hash of consent text shown to user for proof';

-- ============================================================
-- CONSENT AUDIT LOG (Change History)
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consent_id UUID NOT NULL REFERENCES participant_consent(id),

    event_type VARCHAR(50) NOT NULL,
        -- CONSENT_REQUESTED, CONSENT_GRANTED, CONSENT_DECLINED,
        -- CONSENT_WITHDRAWN, CONSENT_EXPIRED, DATA_DELETED

    event_details JSONB NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Actor (who performed the action)
    actor_type VARCHAR(20), -- USER, SYSTEM, ADMIN
    actor_id VARCHAR(100),

    -- Audit metadata
    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consent_audit_consent
ON consent_audit_log(consent_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_consent_audit_event
ON consent_audit_log(event_type, event_timestamp DESC);

COMMENT ON TABLE consent_audit_log IS 'Immutable audit log of all consent-related events';

-- ============================================================
-- CONSENT PREFERENCES (User-Level)
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    participant_email VARCHAR(255) UNIQUE NOT NULL,

    -- Global preferences (apply to all meetings)
    default_consent_voice_recording BOOLEAN DEFAULT FALSE,
    default_consent_analytics BOOLEAN DEFAULT FALSE,
    default_consent_meeting_summaries BOOLEAN DEFAULT TRUE,

    -- Opt-out preferences
    global_opt_out BOOLEAN DEFAULT FALSE,
        -- If TRUE, user must explicitly opt-in for each meeting

    -- Communication preferences
    pre_meeting_consent_email BOOLEAN DEFAULT TRUE,
    post_meeting_summary_email BOOLEAN DEFAULT TRUE,

    -- Jurisdiction override (for users who travel)
    preferred_jurisdiction VARCHAR(10),
        -- GDPR_EU, GDPR_UK, CCPA_CA, US_TWO_PARTY, US_ONE_PARTY

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consent_prefs_email
ON consent_preferences(participant_email);

COMMENT ON TABLE consent_preferences IS 'User-level consent preferences for recurring meetings';

-- ============================================================
-- MEETING CONSENT STATUS (Aggregate View)
-- ============================================================

CREATE OR REPLACE VIEW v_meeting_consent_status AS
SELECT
    meeting_id,
    session_id,
    COUNT(*) AS total_participants,
    SUM(CASE WHEN consent_status = 'GRANTED' THEN 1 ELSE 0 END) AS consented_participants,
    SUM(CASE WHEN consent_status = 'PENDING' THEN 1 ELSE 0 END) AS pending_participants,
    SUM(CASE WHEN consent_status = 'DECLINED' THEN 1 ELSE 0 END) AS declined_participants,
    SUM(CASE WHEN consent_status = 'WITHDRAWN' THEN 1 ELSE 0 END) AS withdrawn_participants,
    BOOL_AND(
        consent_status = 'GRANTED' AND
        consent_voice_recording = TRUE
    ) AS all_consented,
    MAX(consent_requested_at) AS last_consent_request,
    MAX(consent_granted_at) AS last_consent_granted
FROM participant_consent
WHERE consent_status != 'EXPIRED'
GROUP BY meeting_id, session_id;

COMMENT ON VIEW v_meeting_consent_status IS 'Real-time consent status for meetings';

-- ============================================================
-- CONSENT WITHDRAWAL PROCESSING
-- ============================================================

-- Function to process consent withdrawal and trigger data deletion
CREATE OR REPLACE FUNCTION withdraw_consent(
    p_consent_token VARCHAR(100),
    p_withdrawal_reason TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_consent_id UUID;
    v_participant_email VARCHAR(255);
    v_session_id VARCHAR(100);
    v_deleted_records JSONB;
BEGIN
    -- Update consent status
    UPDATE participant_consent
    SET
        consent_status = 'WITHDRAWN',
        consent_withdrawn_at = NOW(),
        withdrawal_reason = p_withdrawal_reason,
        withdrawal_method = 'EMAIL_LINK',
        data_deletion_requested = TRUE,
        updated_at = NOW()
    WHERE consent_token = p_consent_token
      AND consent_status = 'GRANTED'
    RETURNING id, participant_email, session_id
    INTO v_consent_id, v_participant_email, v_session_id;

    IF v_consent_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Invalid consent token or consent already withdrawn'
        );
    END IF;

    -- Log withdrawal event
    INSERT INTO consent_audit_log (
        consent_id,
        event_type,
        event_details,
        actor_type
    ) VALUES (
        v_consent_id,
        'CONSENT_WITHDRAWN',
        jsonb_build_object(
            'reason', p_withdrawal_reason,
            'session_id', v_session_id
        ),
        'USER'
    );

    -- Trigger data deletion (in separate function)
    SELECT delete_participant_data(v_session_id, v_participant_email)
    INTO v_deleted_records;

    -- Update consent record with deletion status
    UPDATE participant_consent
    SET
        data_deletion_completed_at = NOW(),
        updated_at = NOW()
    WHERE id = v_consent_id;

    RETURN jsonb_build_object(
        'success', true,
        'consent_id', v_consent_id,
        'participant_email', v_participant_email,
        'withdrawn_at', NOW(),
        'deleted_records', v_deleted_records
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION withdraw_consent IS 'Processes consent withdrawal and triggers data deletion';

-- ============================================================
-- DATA DELETION FUNCTION (Implements Right to Erasure)
-- ============================================================

CREATE OR REPLACE FUNCTION delete_participant_data(
    p_session_id VARCHAR(100),
    p_participant_email VARCHAR(255)
)
RETURNS JSONB AS $$
DECLARE
    v_deleted_count JSONB;
BEGIN
    -- Delete from tool_executions
    WITH deleted_tool_exec AS (
        DELETE FROM tool_executions
        WHERE session_id = p_session_id
          AND voice_response LIKE '%' || p_participant_email || '%'
        RETURNING id
    ),
    -- Delete from tool_calls
    deleted_tool_calls AS (
        DELETE FROM tool_calls
        WHERE session_id = p_session_id
        RETURNING id
    ),
    -- Delete from session_context
    deleted_session_ctx AS (
        DELETE FROM session_context
        WHERE session_id = p_session_id
        RETURNING id
    ),
    -- Delete from training_metrics
    deleted_training AS (
        DELETE FROM training_metrics
        WHERE user_email = p_participant_email
          AND session_id = p_session_id
        RETURNING id
    ),
    -- Delete from user_session_analytics
    deleted_analytics AS (
        DELETE FROM user_session_analytics
        WHERE user_email = p_participant_email
          AND session_id = p_session_id
        RETURNING id
    ),
    -- Anonymize audit_trail (retain for legal compliance)
    anonymized_audit AS (
        UPDATE audit_trail
        SET user_email = 'REDACTED_' || LEFT(MD5(user_email), 8)
        WHERE session_id = p_session_id
          AND user_email = p_participant_email
        RETURNING id
    )
    SELECT jsonb_build_object(
        'tool_executions_deleted', (SELECT COUNT(*) FROM deleted_tool_exec),
        'tool_calls_deleted', (SELECT COUNT(*) FROM deleted_tool_calls),
        'session_context_deleted', (SELECT COUNT(*) FROM deleted_session_ctx),
        'training_metrics_deleted', (SELECT COUNT(*) FROM deleted_training),
        'analytics_deleted', (SELECT COUNT(*) FROM deleted_analytics),
        'audit_trail_anonymized', (SELECT COUNT(*) FROM anonymized_audit),
        'deletion_timestamp', NOW()
    ) INTO v_deleted_count;

    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION delete_participant_data IS 'Deletes participant data from all tables (GDPR Right to Erasure)';

-- ============================================================
-- CONSENT EXPIRY CLEANUP (Scheduled Job)
-- ============================================================

CREATE OR REPLACE FUNCTION expire_old_consents()
RETURNS INTEGER AS $$
DECLARE
    v_expired_count INTEGER;
BEGIN
    -- Expire consents older than 1 year (configurable)
    UPDATE participant_consent
    SET
        consent_status = 'EXPIRED',
        updated_at = NOW()
    WHERE consent_status = 'GRANTED'
      AND consent_granted_at < NOW() - INTERVAL '1 year'
      AND consent_expiry_date IS NULL;

    GET DIAGNOSTICS v_expired_count = ROW_COUNT;

    -- Log expiry events
    INSERT INTO consent_audit_log (
        consent_id,
        event_type,
        event_details,
        actor_type
    )
    SELECT
        id,
        'CONSENT_EXPIRED',
        jsonb_build_object(
            'reason', 'Automatic expiry after 1 year',
            'expired_at', NOW()
        ),
        'SYSTEM'
    FROM participant_consent
    WHERE consent_status = 'EXPIRED'
      AND updated_at > NOW() - INTERVAL '1 minute';

    RETURN v_expired_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_consents IS 'Expires consents older than 1 year (run daily)';
```

### 4.2 Consent Workflow Integration Points

**Table Integration with Existing Schema:**

```sql
-- ============================================================
-- INTEGRATION WITH EXISTING VOICE AGENT SCHEMA
-- ============================================================

-- Alter tool_calls to reference consent
ALTER TABLE tool_calls
ADD COLUMN consent_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN consent_id UUID REFERENCES participant_consent(id);

COMMENT ON COLUMN tool_calls.consent_verified IS 'TRUE if participant consent verified before tool execution';

-- Alter audit_trail to reference consent
ALTER TABLE audit_trail
ADD COLUMN consent_id UUID REFERENCES participant_consent(id);

-- Alter user_session_analytics to track consent status
ALTER TABLE user_session_analytics
ADD COLUMN consent_status VARCHAR(20),
ADD COLUMN consent_granted_at TIMESTAMPTZ,
ADD COLUMN consent_withdrawn_at TIMESTAMPTZ;

-- View: Sessions with consent issues
CREATE OR REPLACE VIEW v_sessions_without_consent AS
SELECT
    usa.session_id,
    usa.user_email,
    usa.started_at,
    usa.total_interactions,
    pc.consent_status,
    pc.jurisdiction
FROM user_session_analytics usa
LEFT JOIN participant_consent pc
    ON usa.session_id = pc.session_id
    AND usa.user_email = pc.participant_email
WHERE pc.consent_status IS NULL
   OR pc.consent_status != 'GRANTED';

COMMENT ON VIEW v_sessions_without_consent IS 'Sessions without valid consent (compliance risk)';
```

---

## 5. API Endpoint Specifications

### 5.1 Consent Request API

**Endpoint:** `POST /api/v1/consent/request`

**Description:** Initiates consent request for meeting participant

**Request:**
```json
{
  "meeting_id": "teams_abc123",
  "session_id": "sess_xyz789",
  "participant_email": "user@example.com",
  "participant_name": "John Doe",
  "participant_id": "teams_user_456",
  "jurisdiction": "GDPR_EU",
  "consent_method": "PRE_MEETING_EMAIL",
  "meeting_metadata": {
    "meeting_title": "Q1 Planning Session",
    "meeting_date": "2026-01-20T14:00:00Z",
    "host_name": "Jane Smith",
    "host_email": "jane@example.com"
  }
}
```

**Response:**
```json
{
  "success": true,
  "consent_id": "550e8400-e29b-41d4-a716-446655440000",
  "consent_token": "cnst_abc123xyz",
  "consent_url": "https://synrgscaling.com/consent?token=cnst_abc123xyz",
  "email_sent": true,
  "expires_at": "2026-01-20T13:30:00Z"
}
```

**Error Codes:**
- `400` - Invalid request (missing required fields)
- `409` - Consent already exists for participant/meeting
- `500` - Internal server error

---

### 5.2 Consent Grant API

**Endpoint:** `POST /api/v1/consent/grant`

**Description:** Records participant consent grant

**Request:**
```json
{
  "consent_token": "cnst_abc123xyz",
  "consent_options": {
    "consent_voice_recording": true,
    "consent_transcription": true,
    "consent_ai_processing": true,
    "consent_analytics": false,
    "consent_international_transfer": true,
    "consent_meeting_summaries": true
  },
  "metadata": {
    "ip_address": "192.0.2.1",
    "user_agent": "Mozilla/5.0...",
    "consent_version": "1.0",
    "consent_text_hash": "sha256:abc123..."
  }
}
```

**Response:**
```json
{
  "success": true,
  "consent_id": "550e8400-e29b-41d4-a716-446655440000",
  "consent_status": "GRANTED",
  "granted_at": "2026-01-17T10:30:00Z",
  "participant_email": "user@example.com",
  "meeting_id": "teams_abc123"
}
```

---

### 5.3 Consent Status API

**Endpoint:** `GET /api/v1/consent/status/{meeting_id}`

**Description:** Returns consent status for all participants in a meeting

**Response:**
```json
{
  "success": true,
  "meeting_id": "teams_abc123",
  "total_participants": 5,
  "consented_participants": 3,
  "pending_participants": 2,
  "declined_participants": 0,
  "all_consented": false,
  "participants": [
    {
      "participant_email": "user1@example.com",
      "participant_name": "John Doe",
      "consent_status": "GRANTED",
      "granted_at": "2026-01-17T10:30:00Z",
      "jurisdiction": "GDPR_EU",
      "consent_options": {
        "voice_recording": true,
        "analytics": false
      }
    },
    {
      "participant_email": "user2@example.com",
      "participant_name": "Jane Smith",
      "consent_status": "PENDING",
      "requested_at": "2026-01-17T10:00:00Z"
    }
  ]
}
```

---

### 5.4 Consent Withdrawal API

**Endpoint:** `POST /api/v1/consent/withdraw`

**Description:** Processes consent withdrawal and triggers data deletion

**Request:**
```json
{
  "consent_token": "cnst_abc123xyz",
  "withdrawal_reason": "I no longer want my data stored",
  "confirm_deletion": true
}
```

**Response:**
```json
{
  "success": true,
  "consent_id": "550e8400-e29b-41d4-a716-446655440000",
  "withdrawn_at": "2026-01-17T11:00:00Z",
  "data_deletion_scheduled": true,
  "deletion_completed_by": "2026-01-20T11:00:00Z",
  "deleted_records": {
    "tool_executions_deleted": 5,
    "tool_calls_deleted": 3,
    "session_context_deleted": 2,
    "training_metrics_deleted": 8,
    "analytics_deleted": 1,
    "audit_trail_anonymized": 12
  }
}
```

---

### 5.5 Consent Preferences API

**Endpoint:** `GET /api/v1/consent/preferences/{email}`

**Description:** Returns user's global consent preferences

**Response:**
```json
{
  "success": true,
  "participant_email": "user@example.com",
  "preferences": {
    "default_consent_voice_recording": false,
    "default_consent_analytics": false,
    "default_consent_meeting_summaries": true,
    "global_opt_out": false,
    "pre_meeting_consent_email": true,
    "post_meeting_summary_email": true,
    "preferred_jurisdiction": "GDPR_EU"
  },
  "updated_at": "2026-01-17T10:00:00Z"
}
```

**Endpoint:** `PUT /api/v1/consent/preferences/{email}`

**Description:** Updates user's global consent preferences

**Request:**
```json
{
  "preferences": {
    "default_consent_analytics": true,
    "global_opt_out": false
  }
}
```

---

## 6. n8n Workflow Design

### 6.1 Consent Request Workflow

**Workflow Name:** "Voice Agent - Consent Request Handler"

**Trigger:** Webhook (`POST /webhook/consent/request`)

**Nodes:**

```
1. Webhook Trigger
   ├─ Method: POST
   ├─ Path: /webhook/consent/request
   └─ Authentication: Header auth (X-API-Key)

2. Detect Participant Jurisdiction
   ├─ Function: Extract email domain
   ├─ Logic: Map domain to jurisdiction
   │   • @*.eu → GDPR_EU
   │   • @*.uk → GDPR_UK
   │   • @*.ca → CCPA_CA
   │   • Default → US_ONE_PARTY
   └─ Output: jurisdiction variable

3. Generate Consent Token
   ├─ Function: crypto.randomUUID()
   ├─ Format: "cnst_" + uuid.substring(0, 12)
   └─ Output: consent_token

4. Postgres: Insert Consent Record
   ├─ Table: participant_consent
   ├─ Query: INSERT INTO participant_consent (...)
   ├─ Return: consent_id
   └─ On Error: Return 409 if duplicate

5. Switch: Consent Method
   ├─ PRE_MEETING_EMAIL → Node 6
   ├─ IN_MEETING_CHAT → Node 8
   └─ WEB_FORM → Node 10

6. Gmail: Send Pre-Meeting Consent Email
   ├─ Template: GDPR Pre-Meeting Email (Section 2.1)
   ├─ Attachments: Privacy Notice PDF
   ├─ Consent URL: https://synrgscaling.com/consent?token={{consent_token}}
   └─ Track: Email sent timestamp

7. Postgres: Update Consent Record
   ├─ Query: UPDATE participant_consent SET email_sent_at = NOW()
   └─ Return: Updated record

8. Teams Chat: Send In-Meeting Banner
   ├─ Template: In-Meeting Bot Announcement (Section 2.2)
   ├─ Buttons: "I CONSENT" | "I DO NOT CONSENT"
   └─ Callback: /webhook/consent/grant

9. Respond to Webhook
   ├─ Status: 200 OK
   ├─ Body: { success: true, consent_id, consent_token, consent_url }
   └─ End workflow
```

---

### 6.2 Consent Grant Workflow

**Workflow Name:** "Voice Agent - Consent Grant Handler"

**Trigger:** Webhook (`POST /webhook/consent/grant`)

**Nodes:**

```
1. Webhook Trigger
   ├─ Method: POST
   ├─ Path: /webhook/consent/grant
   └─ Authentication: Header auth

2. Validate Consent Token
   ├─ Query: SELECT * FROM participant_consent WHERE consent_token = ?
   ├─ Validate: consent_status = 'PENDING'
   └─ On Error: Return 400 "Invalid or expired token"

3. Hash Consent Text
   ├─ Function: crypto.createHash('sha256')
   ├─ Input: consent_text from request
   └─ Output: consent_text_hash

4. Postgres: Update Consent Record
   ├─ Query: UPDATE participant_consent SET
   │   consent_status = 'GRANTED',
   │   consent_granted_at = NOW(),
   │   consent_voice_recording = ?,
   │   consent_analytics = ?,
   │   ...
   ├─ Return: Updated record
   └─ On Error: Return 500

5. Postgres: Insert Audit Log
   ├─ Table: consent_audit_log
   ├─ Event: CONSENT_GRANTED
   └─ Details: IP, user_agent, consent_options

6. Check All Participants Consented
   ├─ Query: SELECT all_consented FROM v_meeting_consent_status
   │          WHERE meeting_id = ?
   └─ Output: all_consented boolean

7. IF: All Participants Consented = TRUE
   ├─ YES → Node 8 (Trigger Bot Recording)
   └─ NO → Node 10 (Notify Pending)

8. HTTP Request: Notify Relay Server
   ├─ URL: {{RELAY_SERVER_URL}}/recording/start
   ├─ Method: POST
   ├─ Body: { session_id, meeting_id, all_consented: true }
   └─ Headers: X-API-Key

9. Teams Chat: Notify Meeting
   ├─ Message: "All participants have consented. Recording starting now."
   └─ End workflow

10. Teams Chat: Update Status
    ├─ Message: "Waiting for consent from: [PENDING PARTICIPANTS]"
    └─ End workflow
```

---

### 6.3 Consent Withdrawal Workflow

**Workflow Name:** "Voice Agent - Consent Withdrawal Handler"

**Trigger:** Webhook (`POST /webhook/consent/withdraw`)

**Nodes:**

```
1. Webhook Trigger
   ├─ Method: POST
   ├─ Path: /webhook/consent/withdraw
   └─ Query Param: consent_token

2. Postgres: Call withdraw_consent() Function
   ├─ Query: SELECT withdraw_consent(?, ?)
   ├─ Parameters: consent_token, withdrawal_reason
   └─ Return: { success, deleted_records }

3. IF: Withdrawal Successful
   ├─ YES → Node 4
   └─ NO → Node 7 (Error Response)

4. Gmail: Send Withdrawal Confirmation Email
   ├─ Subject: "Consent Withdrawn - Data Deletion Confirmed"
   ├─ Body: "Your consent has been withdrawn and your data deleted"
   ├─ Include: Deletion summary (records deleted)
   └─ Track: Email sent

5. HTTP Request: Notify Vendors
   ├─ Recall.ai: DELETE /bot/{bot_id}/participant/{participant_id}
   ├─ Deepgram: Request transcript deletion
   ├─ Groq: Request context deletion
   └─ Cartesia: Request audio deletion

6. Respond to Webhook
   ├─ Status: 200 OK
   ├─ Body: { success: true, withdrawn_at, deleted_records }
   └─ End workflow

7. Error Response
   ├─ Status: 400 Bad Request
   ├─ Body: { success: false, error: "Invalid consent token" }
   └─ End workflow
```

---

### 6.4 Mid-Meeting Participant Join Workflow

**Workflow Name:** "Voice Agent - Mid-Meeting Consent Handler"

**Trigger:** Recall.ai webhook (`participant.joined`)

**Nodes:**

```
1. Webhook Trigger
   ├─ Source: Recall.ai
   ├─ Event: participant.joined
   └─ Payload: { session_id, participant_id, participant_email, joined_at }

2. Check Existing Consent
   ├─ Query: SELECT * FROM participant_consent
   │          WHERE session_id = ? AND participant_email = ?
   └─ Output: existing_consent (or NULL)

3. IF: Consent Exists
   ├─ YES → End workflow (already handled)
   └─ NO → Node 4 (Request consent)

4. Pause Recording for New Participant
   ├─ HTTP Request: {{RELAY_SERVER_URL}}/recording/pause
   ├─ Body: { session_id, participant_id, reason: "awaiting_consent" }
   └─ Response: { paused: true }

5. Teams Chat: Notify Late Joiner
   ├─ Template: Mid-Meeting Consent (Section 2.3)
   ├─ Buttons: "I CONSENT" | "I DO NOT CONSENT"
   └─ Callback: /webhook/consent/grant

6. Teams Chat: Notify Other Participants
   ├─ Message: "[PARTICIPANT NAME] joined. Waiting for their consent..."
   └─ End workflow (resumes when consent granted in Workflow 6.2)
```

---

## 7. Implementation Checklist

### 7.1 Phase 1: Database & Backend (Week 1-2)

- [ ] **Database Schema**
  - [ ] Create `participant_consent` table
  - [ ] Create `consent_audit_log` table
  - [ ] Create `consent_preferences` table
  - [ ] Create views (`v_meeting_consent_status`, `v_sessions_without_consent`)
  - [ ] Create functions (`withdraw_consent()`, `delete_participant_data()`, `expire_old_consents()`)
  - [ ] Alter existing tables to reference consent (`tool_calls`, `audit_trail`, `user_session_analytics`)
  - [ ] Test all SQL functions and triggers

- [ ] **API Endpoints**
  - [ ] Implement `/api/v1/consent/request` (POST)
  - [ ] Implement `/api/v1/consent/grant` (POST)
  - [ ] Implement `/api/v1/consent/status/{meeting_id}` (GET)
  - [ ] Implement `/api/v1/consent/withdraw` (POST)
  - [ ] Implement `/api/v1/consent/preferences/{email}` (GET/PUT)
  - [ ] Add authentication/authorization for all endpoints
  - [ ] Add rate limiting to prevent abuse
  - [ ] Write API documentation (OpenAPI/Swagger)

- [ ] **Jurisdiction Detection**
  - [ ] Implement email domain → jurisdiction mapping
  - [ ] Implement IP geolocation fallback
  - [ ] Create jurisdiction rules engine
  - [ ] Test with EU, UK, CA, US addresses

---

### 7.2 Phase 2: n8n Workflows (Week 2-3)

- [ ] **Workflow 1: Consent Request Handler**
  - [ ] Create webhook trigger
  - [ ] Implement jurisdiction detection logic
  - [ ] Generate consent tokens
  - [ ] Insert consent records into database
  - [ ] Send pre-meeting consent emails (GDPR/UK/CCPA templates)
  - [ ] Test with different jurisdictions

- [ ] **Workflow 2: Consent Grant Handler**
  - [ ] Create webhook trigger
  - [ ] Validate consent tokens
  - [ ] Update consent records in database
  - [ ] Insert audit log entries
  - [ ] Check if all participants consented
  - [ ] Notify relay server to start recording
  - [ ] Send Teams chat updates
  - [ ] Test consent grant flow end-to-end

- [ ] **Workflow 3: Consent Withdrawal Handler**
  - [ ] Create webhook trigger
  - [ ] Call `withdraw_consent()` database function
  - [ ] Trigger data deletion across all tables
  - [ ] Send withdrawal confirmation email
  - [ ] Notify vendors (Recall.ai, Deepgram, etc.) to delete data
  - [ ] Test withdrawal and verify data deletion

- [ ] **Workflow 4: Mid-Meeting Consent Handler**
  - [ ] Listen to Recall.ai `participant.joined` webhook
  - [ ] Check for existing consent
  - [ ] Pause recording for new participant
  - [ ] Send in-meeting consent request
  - [ ] Resume recording when consent granted
  - [ ] Test late joiner scenario

---

### 7.3 Phase 3: UI/UX (Week 3-4)

- [ ] **Consent Web Forms**
  - [ ] Create GDPR consent form page
  - [ ] Create UK GDPR consent form page
  - [ ] Create CCPA/CPRA notice page
  - [ ] Create two-party consent notice page
  - [ ] Implement multi-language support (EN, FR, DE, ES)
  - [ ] Add consent text version tracking
  - [ ] Test form submission and validation

- [ ] **Email Templates**
  - [ ] Create pre-meeting consent email (GDPR)
  - [ ] Create pre-meeting consent email (UK GDPR)
  - [ ] Create pre-meeting consent email (CCPA)
  - [ ] Create post-meeting summary email with withdrawal link
  - [ ] Create withdrawal confirmation email
  - [ ] Test email delivery and link functionality

- [ ] **Teams Chat Integration**
  - [ ] Implement bot announcement message
  - [ ] Add interactive consent buttons
  - [ ] Add real-time consent status updates
  - [ ] Add mid-meeting consent notifications
  - [ ] Test chat interactions in Teams

---

### 7.4 Phase 4: Relay Server Integration (Week 4-5)

- [ ] **Consent Verification Before Recording**
  - [ ] Modify relay server to check consent before recording
  - [ ] Add `/recording/start` endpoint (requires all_consented = true)
  - [ ] Add `/recording/pause` endpoint (for late joiners)
  - [ ] Add `/recording/resume` endpoint (when consent granted)
  - [ ] Test recording pause/resume logic

- [ ] **Consent Status Polling**
  - [ ] Implement consent status polling in relay server
  - [ ] Add callback to n8n when all participants consented
  - [ ] Test end-to-end consent → recording flow

---

### 7.5 Phase 5: Vendor Data Deletion (Week 5-6)

- [ ] **Recall.ai Integration**
  - [ ] Implement Recall.ai participant deletion API
  - [ ] Test participant removal from active meetings
  - [ ] Test recording deletion after meeting ends

- [ ] **Deepgram Integration**
  - [ ] Contact Deepgram support for data deletion API
  - [ ] Implement deletion requests in withdrawal workflow
  - [ ] Document Deepgram retention policy

- [ ] **Groq Integration**
  - [ ] Contact Groq support for data deletion API
  - [ ] Implement deletion requests in withdrawal workflow
  - [ ] Document Groq retention policy

- [ ] **Cartesia Integration**
  - [ ] Contact Cartesia support for data deletion API
  - [ ] Implement deletion requests in withdrawal workflow
  - [ ] Document Cartesia retention policy

- [ ] **Supabase Integration**
  - [ ] Verify automated deletion functions work
  - [ ] Test backup/restore with deleted data
  - [ ] Document Supabase retention policy

---

### 7.6 Phase 6: Testing & Validation (Week 6-7)

- [ ] **Unit Tests**
  - [ ] Test database functions (withdraw_consent, delete_participant_data)
  - [ ] Test jurisdiction detection logic
  - [ ] Test consent token generation
  - [ ] Test API endpoints (request, grant, status, withdraw)

- [ ] **Integration Tests**
  - [ ] Test end-to-end consent flow (GDPR)
  - [ ] Test end-to-end consent flow (UK GDPR)
  - [ ] Test end-to-end consent flow (CCPA)
  - [ ] Test end-to-end consent flow (two-party consent states)
  - [ ] Test mid-meeting consent flow
  - [ ] Test consent withdrawal flow
  - [ ] Test data deletion verification

- [ ] **User Acceptance Testing**
  - [ ] Test pre-meeting consent email delivery
  - [ ] Test consent form usability
  - [ ] Test in-meeting consent notifications
  - [ ] Test withdrawal link functionality
  - [ ] Test multi-language support

- [ ] **Compliance Testing**
  - [ ] Verify GDPR Article 9 compliance (explicit consent)
  - [ ] Verify UK GDPR compliance (ICO guidance)
  - [ ] Verify CCPA notice at collection
  - [ ] Verify two-party consent compliance
  - [ ] Verify data deletion within 72 hours
  - [ ] Verify audit trail completeness

---

### 7.7 Phase 7: Documentation & Training (Week 7-8)

- [ ] **Legal Documentation**
  - [ ] Draft GDPR privacy notice
  - [ ] Draft UK GDPR privacy notice
  - [ ] Draft CCPA privacy notice
  - [ ] Draft Data Processing Agreements (DPAs) for vendors
  - [ ] Conduct Data Protection Impact Assessment (DPIA)
  - [ ] Document legal basis for processing

- [ ] **Technical Documentation**
  - [ ] Document API endpoints (OpenAPI spec)
  - [ ] Document database schema
  - [ ] Document n8n workflows
  - [ ] Document consent flow diagrams
  - [ ] Document vendor deletion procedures

- [ ] **User Documentation**
  - [ ] Create participant consent FAQ
  - [ ] Create host consent setup guide
  - [ ] Create withdrawal process guide
  - [ ] Create multi-language documentation

- [ ] **Staff Training**
  - [ ] Train support team on consent process
  - [ ] Train engineering team on compliance requirements
  - [ ] Train sales team on consent disclosures
  - [ ] Train legal team on DPIA and incident response

---

### 7.8 Phase 8: Deployment & Monitoring (Week 8)

- [ ] **Deployment**
  - [ ] Deploy database schema to production
  - [ ] Deploy API endpoints to production
  - [ ] Deploy n8n workflows to production
  - [ ] Deploy consent web forms to production
  - [ ] Configure monitoring and alerting

- [ ] **Monitoring**
  - [ ] Set up consent request monitoring
  - [ ] Set up consent grant rate monitoring
  - [ ] Set up withdrawal request monitoring
  - [ ] Set up data deletion verification monitoring
  - [ ] Set up compliance dashboard

- [ ] **Incident Response**
  - [ ] Document consent breach procedures
  - [ ] Document data deletion failure procedures
  - [ ] Test incident response plan
  - [ ] Train team on incident response

---

## 8. Compliance Validation Criteria

### 8.1 GDPR Compliance Checklist

- [ ] **Article 6 (Lawfulness)**
  - [ ] Legal basis identified for each processing purpose
  - [ ] Consent obtained before processing begins
  - [ ] Consent is freely given (no conditionality)

- [ ] **Article 9 (Special Categories)**
  - [ ] Explicit consent obtained for biometric data
  - [ ] No pre-ticked boxes
  - [ ] Separate consent for each purpose

- [ ] **Article 13 (Information to be provided)**
  - [ ] Identity and contact details of controller provided
  - [ ] Contact details of DPO provided
  - [ ] Purposes and legal basis disclosed
  - [ ] Recipients of data disclosed
  - [ ] Retention periods disclosed
  - [ ] Rights of data subjects disclosed

- [ ] **Article 15-22 (Data Subject Rights)**
  - [ ] Right of access implemented
  - [ ] Right to rectification implemented
  - [ ] Right to erasure implemented (within 72 hours)
  - [ ] Right to restrict processing implemented
  - [ ] Right to data portability implemented
  - [ ] Right to object implemented
  - [ ] Right to withdraw consent implemented

- [ ] **Article 25 (Data Protection by Design)**
  - [ ] Consent required before recording starts
  - [ ] Data minimization (voice deleted after transcription)
  - [ ] Pseudonymization in analytics tables
  - [ ] Encryption at rest and in transit

- [ ] **Article 30 (Records of Processing)**
  - [ ] ROPA documented for all processing activities
  - [ ] Consent audit trail maintained

- [ ] **Article 35 (DPIA)**
  - [ ] DPIA conducted for biometric processing
  - [ ] DPIA reviewed annually

---

### 8.2 UK GDPR Compliance Checklist

- [ ] **ICO Guidance on Voice Recordings**
  - [ ] Voice recordings identified as biometric data
  - [ ] Explicit consent obtained
  - [ ] ICO contact details provided

- [ ] **International Transfers**
  - [ ] UK IDTA or UK Addendum to SCCs executed
  - [ ] Transfer impact assessment conducted

---

### 8.3 CCPA/CPRA Compliance Checklist

- [ ] **Notice at Collection**
  - [ ] Categories of PI collected disclosed
  - [ ] Purposes of processing disclosed
  - [ ] Categories of third parties disclosed

- [ ] **Sensitive Personal Information**
  - [ ] Voice recordings identified as sensitive PI
  - [ ] Consent obtained for processing
  - [ ] Limit use and disclosure option provided

- [ ] **Consumer Rights**
  - [ ] Right to know implemented
  - [ ] Right to delete implemented
  - [ ] Right to correct implemented
  - [ ] Right to opt-out of sale/sharing (N/A - no sale)

- [ ] **Do Not Sell My Info**
  - [ ] Disclosure that data is not sold
  - [ ] Link provided (even if not selling)

---

## 9. Post-Implementation Maintenance

### 9.1 Daily Tasks

- [ ] Monitor consent request failures
- [ ] Monitor withdrawal request processing
- [ ] Monitor data deletion completion
- [ ] Review consent audit log for anomalies

### 9.2 Weekly Tasks

- [ ] Review consent grant rates by jurisdiction
- [ ] Review withdrawal reasons
- [ ] Test consent email delivery
- [ ] Review vendor deletion confirmations

### 9.3 Monthly Tasks

- [ ] Run consent expiry cleanup (`expire_old_consents()`)
- [ ] Review consent preferences by user
- [ ] Audit data deletion logs
- [ ] Review GDPR/CCPA compliance metrics

### 9.4 Quarterly Tasks

- [ ] Conduct consent flow penetration test
- [ ] Review and update consent text for legal changes
- [ ] Conduct DPIA review
- [ ] Audit vendor DPAs for compliance

### 9.5 Annual Tasks

- [ ] Conduct full GDPR compliance audit
- [ ] Update privacy notices for regulatory changes
- [ ] Review and update consent workflows
- [ ] Conduct staff training refresher

---

## 10. Risk Mitigation

### 10.1 Identified Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Participant joins without consent** | HIGH | Pause recording until consent granted |
| **Consent email not delivered** | MEDIUM | Retry mechanism + in-meeting fallback |
| **Withdrawal request failure** | HIGH | Manual review queue + 72-hour SLA |
| **Vendor fails to delete data** | HIGH | Regular vendor audits + DPA enforcement |
| **Jurisdiction misidentification** | MEDIUM | Default to strictest (GDPR) + manual override |
| **Consent expiry not enforced** | MEDIUM | Daily cleanup cron job + monitoring |
| **Database failure during withdrawal** | HIGH | Transaction rollback + retry mechanism |

---

## 11. Success Metrics

### 11.1 Consent Collection KPIs

- **Consent Request Rate**: 100% of participants receive consent request
- **Consent Grant Rate**: Target >80% consent grant rate
- **Pre-Meeting Consent Rate**: Target >60% consent granted before meeting
- **Email Delivery Rate**: Target >98% email delivery success
- **Consent Response Time**: Target <5 minutes median response time

### 11.2 Compliance KPIs

- **Withdrawal Processing SLA**: 100% processed within 72 hours
- **Data Deletion Completion Rate**: 100% of requests completed
- **Consent Audit Trail Integrity**: 100% of consents logged
- **Privacy Notice Accessibility**: 100% uptime for consent forms
- **Vendor Deletion Confirmation**: 100% of vendors confirm deletion

---

## Document Control

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-17 | ConsentMechanismAgent | Initial release |

**Review Schedule:**
- Next review: 2026-02-17 (30 days)
- Annual review: 2027-01-17

**Approvals Required:**
- [ ] Legal Team
- [ ] Data Protection Officer
- [ ] Engineering Lead
- [ ] Product Manager
- [ ] Executive Sponsor

---

**END OF CONSENT MECHANISM DESIGN DOCUMENT**
