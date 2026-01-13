# Google Drive Node Schema - Distilled Summary

**Node Type:** `n8n-nodes-base.googleDrive`
**Latest Version:** 3
**Category:** Input
**AI Tool:** No
**Trigger/Webhook:** No

---

## Authentication

| Option | Value | Recommended |
|--------|-------|-------------|
| OAuth2 | `oAuth2` | Yes (default) |
| Service Account | `serviceAccount` | No |

---

## Resources and Operations

### DRIVE (Shared Drive Management)

Manage shared drives across the organization.

| Operation | Value | Description |
|-----------|-------|-------------|
| Create | `create` | Create a new shared drive |
| Get | `get` | Retrieve details of a specific shared drive |
| Get Many | `list` | List all shared drives (with pagination) |
| Update | `update` | Modify shared drive properties |
| Delete | `deleteDrive` | Permanently delete a shared drive |

**Shared Drive Parameters:**
- `driveId` (resourceLocator): Select or specify shared drive via list/URL/ID
- `name` (string): Name for new drives
- Options include: `colorRgb`, `hidden`, restrictions (copy/domain/members-only), capabilities

---

### FILE (File Operations)

Core file management operations.

| Operation | Value | Description |
|-----------|-------|-------------|
| Upload | `upload` | Upload file to Google Drive |
| Download | `download` | Download file content |
| Copy | `copy` | Duplicate an existing file |
| Move | `move` | Move file to different folder |
| Delete | `deleteFile` | Permanently delete file |
| Share | `share` | Grant sharing permissions |
| Update | `update` | Modify file metadata |
| Create From Text | `createFromText` | Create file from text content |

**File Parameters:**
- `fileId` (resourceLocator): Select/specify file via list/URL/ID
- Common options: parent folder, file name, file content, permissions

---

### FOLDER (Folder Operations)

Directory-level management.

| Operation | Value | Description |
|-----------|-------|-------------|
| Create | `create` | Create new folder |
| Share | `share` | Add sharing permissions to folder |
| Delete | `deleteFolder` | Permanently delete folder |

**Folder Parameters:**
- `folderId` (resourceLocator): Specify target folder
- `name` (string): Folder name for creation

---

### FILE/FOLDER (Search & List)

Combined file/folder discovery.

| Operation | Value | Description |
|-----------|-------|-------------|
| Search | `search` | Search and list files/folders |

**Search Parameters:**
- Query filters, pagination, recursive search options

---

## Key Features

### Resource Locator Modes
All file/folder/drive selection fields support 3 input modes:
1. **List** - Browse and select from available items (searchable)
2. **URL** - Paste Google Drive link (auto-extracts ID)
3. **ID** - Paste file/folder/drive ID directly

### Pagination & Limits
- `returnAll`: Get all results vs. limited set
- `limit`: Configure result count (1-200, default 100)

### Advanced Options by Operation

**Shared Drive Creation:**
- Capabilities configuration (add children, edit, comment, etc.)
- Restrictions (domain users only, member-only, copy restrictions)
- Color customization
- Visibility settings

**File Operations:**
- Parent folder selection
- File naming and metadata
- Permission configuration (read, write, comment access)
- Specific format conversions for Google Workspace formats

**Search:**
- Query syntax (supports regex patterns)
- Recursive folder search
- Pagination controls

---

## Common Use Cases

| Task | Resource | Operation | Notes |
|------|----------|-----------|-------|
| Store workflow outputs | FILE | `upload` | Requires parent folder ID |
| Archive data | FILE | `move` | Move to archive folder |
| Share report | FILE | `share` | Configure permission level |
| Organize files | FOLDER | `create` | Create folder structure |
| Find documents | FILE/FOLDER | `search` | Query-based discovery |
| Backup setup | DRIVE | `create` | Organization-level shared drive |

---

## Credential Configuration

**Required:**
- Google Drive API access
- Service account JSON (for service account auth) OR
- OAuth2 consent grant (for user auth)

**Permissions Needed:**
- `drive` (full access) or scoped permissions
- Admin access for shared drive operations

---

## Validation Notes

- File/folder IDs are alphanumeric with hyphens/underscores
- Shared drive IDs follow same format
- URLs auto-extract via regex validation
- All resourceLocator fields support mixed input modes

---

## AI Integration

**Pre-built Template:** `knowledge_store_agent_with_google_drive`
- Enables AI-powered document analysis
- Retrieve, analyze, and answer questions about Drive documents
- Suggested for RAG (Retrieval-Augmented Generation) workflows

---

## Full Schema File Location

Raw schema saved to: `/Users/jelalconnor/.claude/projects/-Users-jelalconnor-CODING-N8N-Workflows/6bea7375-0db0-4004-b93b-41cbb0fa23f6/tool-results/mcp-n8n-mcp-get_node-1766941359121.txt`

Parse with: `jq '.[] | .text'` to extract JSON
