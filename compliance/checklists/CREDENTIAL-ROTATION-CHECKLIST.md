# Credential Rotation Validation Checklist

**Purpose:** Track rotation of all compromised credentials from security incident
**Target Completion:** Week 0-1 (Emergency Priority)
**Related:** Phase 0 Emergency Stabilization - Item 1
**Status:** ⏳ PENDING

---

## Overview

This checklist provides detailed validation for rotating all 12 credentials exposed in `.mcp.json` git history. Each credential must be rotated, tested, and validated before marking complete.

**Pass Criteria:** 12/12 credentials rotated with verified evidence
**Review Authority:** Security Officer + DevOps Lead
**Documentation Location:** `/compliance/evidence/phase-0/credential-rotation/`

---

## Credential Rotation Protocol

### General Process (Apply to Each Credential)

1. **Generate New Credential**
   - Access vendor dashboard/API
   - Generate new API key/secret
   - Record new credential in secrets manager (NOT in code)
   - Document old credential ID (last 4 characters)

2. **Test New Credential**
   - Deploy to staging/test environment
   - Execute test workflows/API calls
   - Verify functionality identical to old credential
   - Document test results

3. **Deploy to Production**
   - Update secrets manager production values
   - Restart affected services
   - Monitor error logs for 15 minutes
   - Verify production functionality

4. **Revoke Old Credential**
   - Access vendor dashboard/API
   - Immediately revoke/delete old credential
   - Verify old credential no longer works (test should fail)
   - Document revocation timestamp

5. **Update Documentation**
   - Record rotation in credential rotation log
   - Update credential inventory
   - Notify team members (if applicable)

---

## Credential Checklist

### 1. LiveKit API Key + Secret

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** LiveKit Cloud
**Vendor Dashboard:** https://cloud.livekit.io
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key + secret in LiveKit dashboard
- [ ] Store in secrets manager (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`)
- [ ] Test connection in staging (create room, publish stream)
- [ ] Deploy to production
- [ ] Delete old API key from LiveKit dashboard
- [ ] Test old credential fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of LiveKit dashboard showing new API key created
2. Screenshot of old API key deleted
3. Staging test log (successful room creation)
4. Production test log (successful stream publish)
5. Test showing old credential rejected (401/403 error)

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 2. Deepgram API Key

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Deepgram Speech-to-Text
**Vendor Dashboard:** https://console.deepgram.com
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key in Deepgram console
- [ ] Store in secrets manager (`DEEPGRAM_API_KEY`)
- [ ] Test transcription in staging (sample audio file)
- [ ] Deploy to production
- [ ] Delete old API key from Deepgram console
- [ ] Test old credential fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of Deepgram console showing new API key
2. Screenshot of old API key deleted
3. Staging test: transcription result for sample audio
4. Production test: successful transcription
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 3. Groq API Key

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Groq LLM Inference
**Vendor Dashboard:** https://console.groq.com
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key in Groq console
- [ ] Store in secrets manager (`GROQ_API_KEY`)
- [ ] Test LLM inference in staging (sample prompt)
- [ ] Deploy to production
- [ ] Delete old API key from Groq console
- [ ] Test old credential fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of Groq console showing new API key
2. Screenshot of old API key deleted
3. Staging test: LLM completion result
4. Production test: successful inference
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 4. Cartesia API Key

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Cartesia Voice Synthesis
**Vendor Dashboard:** https://play.cartesia.ai (verify URL)
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key in Cartesia dashboard
- [ ] Store in secrets manager (`CARTESIA_API_KEY`)
- [ ] Test voice synthesis in staging (sample text)
- [ ] Deploy to production
- [ ] Delete old API key from Cartesia dashboard
- [ ] Test old credential fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of Cartesia dashboard showing new API key
2. Screenshot of old API key deleted
3. Staging test: synthesized audio file
4. Production test: successful voice generation
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 5. Recall.ai API Key

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Recall.ai Meeting Bot
**Vendor Dashboard:** https://app.recall.ai (verify URL)
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key in Recall.ai dashboard
- [ ] Store in secrets manager (`RECALL_AI_API_KEY`)
- [ ] Test bot creation in staging (test meeting)
- [ ] Deploy to production
- [ ] Delete old API key from Recall.ai dashboard
- [ ] Test old credential fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of Recall.ai dashboard showing new API key
2. Screenshot of old API key deleted
3. Staging test: bot successfully joins test meeting
4. Production test: successful bot operation
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 6. Railway Deployment Token

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Railway Hosting Platform
**Vendor Dashboard:** https://railway.app
**Access:** DevOps Lead account

**Old Credential ID (last 4 chars):** ________
**New Credential ID (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new deployment token in Railway dashboard
- [ ] Store in secrets manager (`RAILWAY_TOKEN`)
- [ ] Update CI/CD pipeline (GitHub Actions, etc.)
- [ ] Test deployment to staging project
- [ ] Deploy to production project
- [ ] Delete old token from Railway dashboard
- [ ] Test old token fails
- [ ] Verify no errors in deployment logs

**Evidence Required:**
1. Screenshot of Railway dashboard showing new token
2. Screenshot of old token deleted
3. Staging deployment log (successful)
4. Production deployment log (successful)
5. Test showing old token rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 7. n8n JWT Secret

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** n8n Workflow Automation
**Credential Type:** JWT Secret (application-generated)
**Access:** n8n environment variables

**Old Secret (last 8 chars):** ________
**New Secret (last 8 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new JWT secret (openssl rand -base64 32)
- [ ] Store in secrets manager (`N8N_JWT_SECRET`)
- [ ] Update n8n environment configuration (staging)
- [ ] Restart n8n service (staging)
- [ ] Test n8n UI login (new sessions use new secret)
- [ ] Deploy to production
- [ ] Restart n8n service (production)
- [ ] Verify existing sessions invalidated (users must re-login)
- [ ] Verify no errors in n8n logs (15 min monitoring)

**Evidence Required:**
1. Command used to generate new secret
2. Secrets manager screenshot showing updated value
3. Staging restart log
4. Production restart log
5. Test showing new login successful

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

**IMPORTANT:** Rotating JWT secret invalidates all existing user sessions. Notify team before production rotation.

---

### 8. PostgreSQL Database Password

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** PostgreSQL Database (MICROSOFT TEAMS AGENT DATABASE)
**Credential ID:** `NI3jbq1U8xPst3j3`
**Access:** Database administrator

**Old Password (last 4 chars):** ________
**New Password (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new password (pwgen -s 32 1 or equivalent)
- [ ] Store in secrets manager (`POSTGRES_PASSWORD`)
- [ ] Connect to PostgreSQL and run: `ALTER USER <username> PASSWORD '<new_password>';`
- [ ] Test new connection in staging
- [ ] Update production application configuration
- [ ] Restart application services
- [ ] Test old password fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. PostgreSQL ALTER USER command output
2. Staging test: successful database query
3. Production test: successful database query
4. Test showing old password rejected
5. Application logs showing no connection errors

**Responsible Party:** Database Administrator
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

**IMPORTANT:** Coordinate rotation with application deployment to avoid connection errors.

---

### 9. Supabase Connection String

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Supabase Database + Auth
**Vendor Dashboard:** https://app.supabase.com
**Access:** DevOps Lead account

**Old Password (last 4 chars):** ________
**New Password (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Access Supabase project settings
- [ ] Reset database password
- [ ] Copy new connection string
- [ ] Store in secrets manager (`SUPABASE_CONNECTION_STRING`)
- [ ] Test connection in staging
- [ ] Deploy to production
- [ ] Verify old connection string fails
- [ ] Verify no errors in application logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of Supabase dashboard showing password reset
2. Staging test: successful database query
3. Production test: successful database query
4. Test showing old connection string rejected
5. Application logs showing no connection errors

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 10. OpenAI API Key

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** OpenAI GPT API
**Credential ID:** `6BIzzQu5jAD5jKlH` (n8n credential ID)
**Vendor Dashboard:** https://platform.openai.com
**Access:** DevOps Lead account

**Old Key (last 4 chars):** ________
**New Key (last 4 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Generate new API key in OpenAI dashboard
- [ ] Store in secrets manager (`OPENAI_API_KEY`)
- [ ] Update n8n credential (ID: `6BIzzQu5jAD5jKlH`)
- [ ] Test LLM completion in staging n8n workflow
- [ ] Deploy to production
- [ ] Delete old API key from OpenAI dashboard
- [ ] Test old credential fails
- [ ] Verify no errors in n8n execution logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of OpenAI dashboard showing new API key
2. Screenshot of old API key deleted
3. Staging test: successful n8n workflow execution with OpenAI node
4. Production test: successful workflow execution
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

### 11. Google OAuth Credentials

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Google Cloud Platform (OAuth 2.0)
**Vendor Dashboard:** https://console.cloud.google.com/apis/credentials
**Access:** Project Owner account

**Old Client ID (last 8 chars):** ________
**New Client ID (last 8 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Create new OAuth 2.0 Client ID in GCP Console
- [ ] Configure authorized redirect URIs
- [ ] Store client ID and secret in secrets manager (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`)
- [ ] Update n8n Google credentials (Gmail, Drive, Sheets, Docs)
- [ ] Test OAuth flow in staging (authorize and fetch data)
- [ ] Deploy to production
- [ ] Delete old OAuth Client ID from GCP Console
- [ ] Test old credential fails
- [ ] Verify no errors in n8n execution logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of GCP Console showing new OAuth Client ID
2. Screenshot of old OAuth Client ID deleted
3. Staging test: successful OAuth authorization and data fetch
4. Production test: successful workflow execution
5. Test showing old credential rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

**IMPORTANT:** Update all n8n credentials using Google OAuth (4 credentials: Gmail, Drive, Sheets, Docs).

---

### 12. Gmail API Credentials

**Status:** ⬜ NOT STARTED | ⏳ IN PROGRESS | ✅ COMPLETE | ❌ FAILED

**Service:** Gmail API (via Google OAuth)
**Credential ID:** `kHDxu9JVLxm6iyMo` (n8n credential ID)
**Vendor Dashboard:** https://console.cloud.google.com
**Access:** Project Owner account

**Old Token (last 8 chars):** ________
**New Token (last 8 chars):** ________
**Rotation Date:** _________
**Rotated By:** _____________________

**Rotation Steps:**
- [ ] Revoke existing Gmail API token in GCP Console (OAuth consent screen)
- [ ] Re-authorize Gmail credential in n8n (ID: `kHDxu9JVLxm6iyMo`)
- [ ] Store new refresh token in secrets manager (if applicable)
- [ ] Test email send in staging n8n workflow
- [ ] Deploy to production
- [ ] Verify old token no longer works
- [ ] Verify no errors in n8n execution logs (15 min monitoring)

**Evidence Required:**
1. Screenshot of GCP Console showing token revoked
2. Screenshot of n8n credential re-authorized
3. Staging test: successful email sent via n8n
4. Production test: successful email sent
5. Test showing old token rejected

**Responsible Party:** DevOps Lead
**Verified By:** _____________________ Date: _________

**Notes:**
_____________________________________________________________________________________

---

## Summary & Completion

### Rotation Progress

| # | Service | Status | Rotated By | Date | Verified By | Date |
|---|---------|--------|------------|------|-------------|------|
| 1 | LiveKit | ⬜ | - | - | - | - |
| 2 | Deepgram | ⬜ | - | - | - | - |
| 3 | Groq | ⬜ | - | - | - | - |
| 4 | Cartesia | ⬜ | - | - | - | - |
| 5 | Recall.ai | ⬜ | - | - | - | - |
| 6 | Railway | ⬜ | - | - | - | - |
| 7 | n8n JWT | ⬜ | - | - | - | - |
| 8 | PostgreSQL | ⬜ | - | - | - | - |
| 9 | Supabase | ⬜ | - | - | - | - |
| 10 | OpenAI | ⬜ | - | - | - | - |
| 11 | Google OAuth | ⬜ | - | - | - | - |
| 12 | Gmail API | ⬜ | - | - | - | - |

**Overall Status:** 0/12 ✅ COMPLETE

---

### Final Verification

**All Credentials Rotated:** ⬜ YES | ⬜ NO
**Evidence Documented:** ⬜ YES | ⬜ NO
**Old Credentials Revoked:** ⬜ YES | ⬜ NO
**No Production Errors:** ⬜ YES | ⬜ NO

**Completion Date:** _________

---

### Approvals

**DevOps Lead:**
Signature: _____________________ Date: _________
Name: _____________________

**Security Officer:**
Signature: _____________________ Date: _________
Name: _____________________

**Phase 0 Item 1 Status:** ⬜ ✅ COMPLETE | ⬜ ❌ BLOCKED

**Blocking Issues (if any):**
_____________________________________________________________________________________
_____________________________________________________________________________________

---

## Post-Rotation Actions

After all 12 credentials are rotated:

1. **Update Credential Inventory**
   - [ ] Update `/compliance/inventory/credential-inventory.csv`
   - [ ] Record new credential IDs and rotation dates

2. **Team Notification**
   - [ ] Notify development team of rotation completion
   - [ ] Share updated secrets manager access procedures

3. **Monitoring**
   - [ ] Monitor application logs for 48 hours post-rotation
   - [ ] Address any errors related to credential changes

4. **Documentation**
   - [ ] Archive rotation evidence in `/compliance/evidence/phase-0/credential-rotation/`
   - [ ] Update incident timeline with rotation completion

5. **Next Rotation Schedule**
   - [ ] Schedule next rotation (90 days for API keys)
   - [ ] Set calendar reminders for rotation team
