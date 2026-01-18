# Google Drive Document Repository

**Workflow ID:** `IamjzfFxjHviJvJg`
**Created:** 2026-01-17
**Status:** Ready for Activation

## Purpose

A voice agent tool workflow that provides access to a Google Drive folder as a live document repository:
- Search files by name or content
- Extract text from documents (PDF, DOCX, TXT, etc.)
- Analyze images using AI vision
- Return structured results for agent consumption

## Target Folder

`https://drive.google.com/drive/folders/11KcezPe3NqgcC3TNvHxAAZS4nPYrMXRF`

## Webhook Endpoint

**Production URL:** `POST https://jayconnorexe.app.n8n.cloud/webhook/drive-document-repo`

## Operations

### 1. List Files
```json
{"operation": "list"}
```

### 2. Search Documents
```json
{"operation": "search", "query": "vacation policy", "limit": 10}
```

### 3. Sync & Extract
```json
{"operation": "sync"}
```

### 4. Get File Content
```json
{"operation": "get", "file_id": "drive-file-id-here"}
```

### 5. Analyze Image
```json
{"operation": "analyze", "file_id": "image-file-id-here"}
```

## Activation

The workflow must be manually activated in the n8n UI:
1. Open workflow `IamjzfFxjHviJvJg` in n8n editor
2. Click the toggle in the top-right to activate
3. Test with: `curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/drive-document-repo -H "Content-Type: application/json" -d '{"operation":"list"}'`

## Architecture

See [docs/architecture.md](./docs/architecture.md)

## Database Tables

- `drive_document_repository` - Stores file metadata and extracted content
- `drive_access_log` - Logs all access operations

## Testing

See [docs/testing.md](./docs/testing.md)
