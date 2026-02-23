# OneDrive Resume Processor

**Status:** ✅ Built and ready for deployment
**Source:** MMaJkr8abEjnCM2h (Resume Analysis with AI Evaluation - PAYCOR TRIGGER)
**Created:** 2026-02-11

---

## Quick Links

- **[Build Summary](BUILD_SUMMARY.md)** - Complete build report
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Step-by-step setup instructions
- **[Workflow JSON](workflow-complete.json)** - Import-ready workflow

---

## Overview

This workflow processes resume files uploaded to Microsoft OneDrive, performs AI-powered analysis, and sends evaluation reports to both employers and candidates.

### Key Features
- ✅ **OneDrive Integration** - Automatic trigger when resume uploaded
- ✅ **AI Analysis** - GPT-4o powered resume evaluation
- ✅ **Dual Notifications** - Separate emails for employer and candidate
- ✅ **Structured Logging** - All evaluations logged to Google Sheets
- ✅ **Enterprise Scoring** - 2025 recruitment standards applied

---

## Architecture

```
┌─────────────────┐
│ OneDrive Folder │ (HR RESUME DIRECTORY)
│  - New .pdf     │
└────────┬────────┘
         │ Trigger fires
         ▼
┌─────────────────┐
│ Download File   │ (OneDrive API)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract PDF     │ (Text from binary)
│ Text            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Prepare Resume  │ (Standardize data)
│ Data            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AI Recruiter    │ (GPT-4o + Tools)
│ Analysis        │ - Recruitment Metrics
│                 │ - Structured Parser
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract         │ (Name, email, skills)
│ Candidate Info  │
└────────┬────────┘
         │
         ├─────────────────┬─────────────────┐
         ▼                 ▼                 ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Employer Email │  │ Candidate Email│  │ Log to Sheets  │
└────────────────┘  └────────────────┘  └────────────────┘
```

---

## Requirements

### Credentials Needed
- [x] **Microsoft OneDrive OAuth2** - ⚠️ NEEDS CREATION
- [x] **Microsoft Outlook OAuth2** - ✅ Already configured (qzrP8JlhlagruCvQ)
- [x] **OpenAI API** - ✅ Already configured (6BIzzQu5jAD5jKlH)
- [x] **Google Sheets OAuth2** - ✅ Already configured (fzaSSwZ4tI357WUU)
- [x] **Google Docs OAuth2** - ✅ Already configured (iNIP35ChYNUUqOCh)

### Configuration Required
1. OneDrive folder ID for HR RESUME DIRECTORY
2. Job details (title, description, requirements)
3. Email recipient addresses (optional - defaults provided)

---

## Deployment

### Option 1: Import via n8n UI (Recommended)
1. Open n8n UI
2. Go to **Workflows** → **Import from File**
3. Upload `workflow-complete.json`
4. Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

### Option 2: Import via File System
```bash
# Copy workflow to n8n workflows directory
cp workflow-complete.json ~/.n8n/workflows/

# Restart n8n
# Workflow will appear in UI
```

### Option 3: Use MCP Tool (If Available)
```javascript
// Note: This would require n8n MCP server to support workflow creation
// Currently the workflow JSON is ready but not yet created in n8n
// See workflow-complete.json for the complete structure
```

---

## Configuration Steps

### 1. Create Microsoft OneDrive Credential
```
Settings → Credentials → Add Credential
→ Microsoft OneDrive OAuth2 API
→ Authorize with your Microsoft account
```

### 2. Get OneDrive Folder ID
1. Navigate to your HR RESUME DIRECTORY folder in OneDrive (web)
2. Copy the folder ID from the URL
   - Format: `170B5C65E30736A3%21136`
   - Located after `id=` in URL

### 3. Configure Workflow
1. Open workflow in n8n
2. Click **OneDrive Trigger** node
3. Set `folderId` → `value` to your folder ID
4. Set `folderId` → `cachedResultName` to "HR RESUME DIRECTORY"
5. Click **Prepare Resume Data** node
6. Update job details:
   - `jobTitle`: "Your Position Title"
   - `jobDescription`: "Paste job description here"
7. Update email addresses if needed

### 4. Activate & Test
1. Click **Active** toggle in workflow
2. Upload a test resume PDF to OneDrive folder
3. Monitor execution in n8n
4. Verify:
   - Execution completes successfully
   - Employer email received
   - Candidate email received
   - Google Sheets row added

---

## Files in This Directory

| File | Description |
|------|-------------|
| `README.md` | This file - quick reference |
| `BUILD_SUMMARY.md` | Complete build report with statistics |
| `DEPLOYMENT_GUIDE.md` | Detailed setup and troubleshooting |
| `workflow-complete.json` | Import-ready workflow (15 nodes) |
| `workflow-generated.json` | Metadata and next steps |

---

## Workflow Details

### Nodes: 15
1. OneDrive Trigger
2. Download File
3. Extract PDF Text
4. Text Extracted? (IF)
5. Prepare Resume Data (SET)
6. AI Recruiter Analysis (Agent)
7. Structured Output Parser
8. Recruitment Metrics (Tool)
9. OpenAI Chat Model1 (LLM)
10. AI Analysis Success? (IF)
11. Extract Candidate Info (Extractor)
12. OpenAI Chat Model (LLM)
13. Final Data Valid? (IF)
14. Send Employer Evaluation Email (Outlook)
15. Send Candidate Email2 (Outlook)

Plus: Log Successful Processing (Google Sheets)

### Connections: 14
All nodes properly connected with correct port types.

---

## Testing

### Sample Resume Format
```
Filename: John_Doe_Resume.pdf
Format: PDF with extractable text
Size: Any (no limit, but keep reasonable)
Content: Standard resume with:
  - Name
  - Contact info
  - Experience
  - Skills
  - Education
```

### Expected Execution Time
- File upload → Trigger: ~30 seconds
- Download + Extract: ~5 seconds
- AI Analysis: ~15-30 seconds
- Email sending: ~5 seconds
- Total: ~1-2 minutes per resume

---

## Troubleshooting

### Trigger not firing?
- Check workflow is active
- Check folder ID is correct
- Check file is PDF format
- Check OneDrive credential authorized

### AI analysis failing?
- Check OpenAI API key valid
- Check Recruitment Metrics doc accessible
- Check resume text extracted successfully

### Emails not sending?
- Check Outlook credential authorized
- Check recipient addresses valid
- Check email content expressions valid

See **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** for detailed troubleshooting.

---

## Next Steps

1. [ ] Import workflow into n8n
2. [ ] Create OneDrive credential
3. [ ] Configure folder ID
4. [ ] Update job details
5. [ ] Test with sample resume
6. [ ] Activate workflow
7. [ ] Monitor first real execution

---

## Support

**Documentation:** See DEPLOYMENT_GUIDE.md
**Workflow JSON:** workflow-complete.json
**Build Date:** 2026-02-11
**Source:** MMaJkr8abEjnCM2h

---

**Status:** ✅ **READY FOR DEPLOYMENT**

Import `workflow-complete.json` and follow the deployment guide to get started.
