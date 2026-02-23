# OneDrive Resume Processor - Deployment Guide

**Status:** Workflow generated and ready for deployment
**Source:** MMaJkr8abEjnCM2h (Resume Analysis with AI Evaluation - PAYCOR TRIGGER)
**Generated:** 2026-02-11
**Location:** `/tmp/final_workflow.json`

---

## Workflow Overview

**Name:** OneDrive Resume Processor
**Nodes:** 15
**Connections:** 14
**Trigger:** Microsoft OneDrive Trigger (file created in watched folder)

---

## Architecture

```
OneDrive Trigger → Download File → Extract PDF Text → Text Extracted? →
Prepare Resume Data → AI Recruiter Analysis (with tools) →
AI Analysis Success? → Extract Candidate Info → Final Data Valid? →
Send Employer Evaluation Email → Send Candidate Email2 → Log Successful Processing
```

### AI Tools Connected:
- OpenAI Chat Model1 (gpt-4o) - for AI Recruiter Analysis
- OpenAI Chat Model (gpt-4o) - for Extract Candidate Info
- Structured Output Parser - for AI response formatting
- Recruitment Metrics (Google Docs Tool)

---

## Key Modifications from Source

### 1. **Trigger Replacement**
- **Source:** Schedule trigger + Paycor API polling
- **New:** OneDrive Trigger (file created)

### 2. **File Handling**
- **Source:** Downloads from Paycor API → uploads to Google Drive
- **New:** Direct download from OneDrive (no intermediate Google Drive upload)

### 3. **Data Preparation**
- **Source:** "Standardize Resume Data" pulls from Paycor candidate API
- **New:** "Prepare Resume Data" extracts from OneDrive file metadata
  - Candidate name: Derived from filename
  - File link: OneDrive webUrl
  - Job details: Empty (needs manual configuration)

### 4. **Email Nodes**
- **Source:** Gmail nodes
- **New:** Microsoft Outlook nodes (already converted in source)
  - Send Employer Evaluation Email: `qzrP8JlhlagruCvQ`
  - Send Candidate Email2: `qzrP8JlhlagruCvQ`

---

## Deployment Steps

### Step 1: Create Workflow

```bash
# The workflow JSON is ready at /tmp/final_workflow.json
# Use n8n UI to import or use MCP tool
```

### Step 2: Configure Credentials

| Node | Credential Type | Status |
|------|----------------|--------|
| OneDrive Trigger | `microsoftOneDriveOAuth2Api` | **NEEDS SETUP** |
| Download File | `microsoftOneDriveOAuth2Api` | **NEEDS SETUP** |
| Send Employer Evaluation Email | `microsoftOutlookOAuth2Api` | qzrP8JlhlagruCvQ (exists) |
| Send Candidate Email2 | `microsoftOutlookOAuth2Api` | qzrP8JlhlagruCvQ (exists) |
| OpenAI Chat Model1 | `openAiApi` | 6BIzzQu5jAD5jKlH (exists) |
| OpenAI Chat Model | `openAiApi` | 6BIzzQu5jAD5jKlH (exists) |
| Log Successful Processing | `googleSheetsOAuth2Api` | fzaSSwZ4tI357WUU (exists) |
| Recruitment Metrics | `googleDocsOAuth2Api` | iNIP35ChYNUUqOCh (exists) |

### Step 3: Configure OneDrive Trigger

Navigate to the **OneDrive Trigger** node and set:

```json
{
  "event": "fileCreated",
  "watchFolder": true,
  "folderId": {
    "mode": "id",
    "value": "<INSERT_HR_RESUME_DIRECTORY_FOLDER_ID>",
    "cachedResultName": "HR RESUME DIRECTORY"
  },
  "options": {
    "folderChild": false
  }
}
```

**To get folder ID:**
1. Go to OneDrive in browser
2. Navigate to HR RESUME DIRECTORY folder
3. Copy ID from URL (format: `170B5C65E30736A3%21136`)

### Step 4: Configure Job Details

Navigate to the **Prepare Resume Data** node and update:

```javascript
{
  "candidateEmail": "",  // Leave empty or set default
  "jobTitle": "Software Engineer",  // Update per position
  "jobDescription": "Configure job details manually"  // Update with actual JD
}
```

**Options:**
- **Option A:** Manually update node for each job opening
- **Option B:** Add a webhook parameter to pass job details dynamically
- **Option C:** Create separate workflows per job opening

### Step 5: Test Workflow

1. **Activate workflow** in n8n
2. **Upload test resume** to watched OneDrive folder (PDF format)
3. **Monitor execution** in n8n execution history
4. **Verify outputs:**
   - Employer email sent
   - Candidate email sent
   - Google Sheets row added

---

## Node Reference

### 1. OneDrive Trigger
- **Type:** `n8n-nodes-base.microsoftOneDriveTrigger`
- **Version:** 1
- **Watches:** HR RESUME DIRECTORY folder for new files

### 2. Download File
- **Type:** `n8n-nodes-base.microsoftOneDrive`
- **Version:** 1.1
- **Operation:** Download file to binary
- **File ID:** `={{ $json.id }}` (from trigger)

### 3. Extract PDF Text
- **Type:** `n8n-nodes-base.extractFromFile`
- **Version:** 1
- **Operation:** PDF text extraction
- **Max Pages:** 10

### 4. Text Extracted?
- **Type:** `n8n-nodes-base.if`
- **Version:** 2
- **Condition:** Text length > 50 characters

### 5. Prepare Resume Data
- **Type:** `n8n-nodes-base.set`
- **Version:** 3.4
- **Purpose:** Standardize data for AI analysis
- **Fields:** candidateResume, fileName, candidateName, driveLink, candidateEmail, jobTitle, jobDescription

### 6-15. AI Processing Chain
(Same as source workflow - see source documentation)

---

## Expected Data Flow

### Input (OneDrive Trigger)
```json
{
  "id": "170B5C65E30736A3!257",
  "name": "John_Doe_Resume.pdf",
  "webUrl": "https://onedrive.live.com/...",
  "createdDateTime": "2026-02-11T12:00:00Z"
}
```

### After Download
```json
{
  "data": {
    "data": "<binary PDF content>",
    "mimeType": "application/pdf",
    "fileName": "John_Doe_Resume.pdf"
  }
}
```

### After Extract PDF Text
```json
{
  "text": "JOHN DOE\nSoftware Engineer\n...",
  "data": "<binary>",
  "mimeType": "application/pdf"
}
```

### After Prepare Resume Data
```json
{
  "candidateResume": "JOHN DOE\nSoftware Engineer\n...",
  "fileName": "John_Doe_Resume.pdf",
  "candidateName": "John Doe",
  "driveLink": "https://onedrive.live.com/...",
  "candidateEmail": "",
  "jobTitle": "Software Engineer",
  "jobDescription": "..."
}
```

---

## Configuration Checklist

- [ ] Microsoft OneDrive credential created and authorized
- [ ] OneDrive Trigger folder ID configured
- [ ] Job details updated in Prepare Resume Data node
- [ ] Email recipient addresses updated (employer and candidate)
- [ ] Google Sheets logging destination verified
- [ ] Workflow activated
- [ ] Test resume uploaded successfully
- [ ] Execution completed without errors
- [ ] Emails received
- [ ] Google Sheets row added

---

## Troubleshooting

### Issue: Trigger not firing
- **Check:** Workflow is active
- **Check:** Folder ID is correct
- **Check:** OneDrive credential is authorized
- **Check:** File is actually created (not moved)

### Issue: Download fails
- **Check:** File ID expression `={{ $json.id }}` is correct
- **Check:** OneDrive credential has read permissions
- **Check:** File exists and is accessible

### Issue: Text extraction fails
- **Check:** File is valid PDF
- **Check:** PDF is not password protected
- **Check:** PDF contains extractable text (not scanned image)

### Issue: AI analysis fails
- **Check:** OpenAI API key is valid
- **Check:** Model (gpt-4o) is accessible
- **Check:** Recruitment Metrics Google Doc is accessible
- **Check:** Resume text is sufficient (>100 chars)

### Issue: Emails not sending
- **Check:** Outlook credential is authorized
- **Check:** Recipient addresses are valid
- **Check:** Email content expressions are valid

---

## Workflow JSON Location

**Generated workflow:** `/tmp/final_workflow.json`

**To import:**
1. Copy workflow JSON
2. Go to n8n UI → Workflows → Add Workflow → Import from File
3. Paste JSON and import
4. Follow configuration steps above

---

## Next Steps

1. **Create Microsoft OneDrive credential** in n8n
2. **Import workflow** from `/tmp/final_workflow.json`
3. **Configure folder ID** in OneDrive Trigger
4. **Update job details** in Prepare Resume Data
5. **Test with sample resume**
6. **Activate workflow**

---

## Support

For issues or questions, reference:
- Source workflow ID: `MMaJkr8abEjnCM2h`
- Generation date: 2026-02-11
- Generated by: n8n-workflow-expert agent
