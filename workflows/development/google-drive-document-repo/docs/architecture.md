# Google Drive Document Repository - Architecture

## Overview

A voice agent tool workflow providing access to a Google Drive folder as a live document repository with database-backed caching and deduplication.

## Target Configuration

- **Folder ID:** `11KcezPe3NqgcC3TNvHxAAZS4nPYrMXRF`
- **Credential:** `jlnNh8eZIxWdsvDS` (Autopayplusworkflows@gmail.com)
- **Database:** PostgreSQL (`drive_document_repository` table)

## Supported Operations

### 1. `list` - List Files
Returns all files in the folder with metadata.

### 2. `search` - Search Documents
Full-text search across extracted content and file names.

### 3. `sync` - Sync & Extract
Scans folder, downloads new/updated files, extracts text, stores in database.
- Deduplicates by `drive_file_id`
- Re-processes if `modifiedTime` changed

### 4. `get` - Get File Content
Retrieves specific file's extracted content from database.

### 5. `analyze` - Analyze Image
Runs AI vision analysis on image files.

## Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WEBHOOK: /drive-document-repo                                               │
│  POST { operation, query?, file_id?, options? }                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     SWITCH: Route Operation   │
                    └───────────────┬───────────────┘
                                    │
        ┌───────────┬───────────┬───┴───┬───────────┬───────────┐
        ▼           ▼           ▼       ▼           ▼           ▼
    ┌───────┐   ┌───────┐   ┌───────┐ ┌───────┐ ┌───────┐   ┌───────┐
    │ list  │   │search │   │ sync  │ │  get  │ │analyze│   │default│
    └───┬───┘   └───┬───┘   └───┬───┘ └───┬───┘ └───┬───┘   └───┬───┘
        │           │           │         │         │           │
        ▼           ▼           │         ▼         ▼           ▼
   [Google      [PostgreSQL     │    [PostgreSQL [Download  [Error
    Drive:       search_        │     SELECT      + Vision   Response]
    List]        documents()]   │     by ID]      Analysis]
        │           │           │         │         │
        ▼           ▼           ▼         ▼         ▼
   [Format      [Format      [SYNC       [Format   [Format
    Response]    Results]    PIPELINE]    File]    Analysis]
                                │
                    ┌───────────▼───────────┐
                    │  SYNC PIPELINE        │
                    │  (Loop over files)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ Check: Needs Processing│
                    │ (Deduplication)        │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
        [SKIP: Already]                    [PROCESS: New/Updated]
        [in database]                             │
                                    ┌─────────────▼─────────────┐
                                    │ SWITCH: Route by MIME Type │
                                    └─────────────┬─────────────┘
                                                  │
                    ┌─────────────┬───────────────┴───────────────┬─────────────┐
                    ▼             ▼                               ▼             ▼
              [PDF Handler] [DOCX Handler]                  [TXT Handler] [Image Handler]
                    │             │                               │             │
                    ▼             ▼                               ▼             ▼
              [Download]    [Convert to                     [Download]    [Download]
                    │        Google Doc]                          │             │
                    ▼             │                               ▼             ▼
              [Read PDF]         ▼                          [Extract]     [AI Vision
               Extract     [Export as                        Content      Analysis]
                    │        Plain Text]                          │             │
                    └─────────────┴───────────────────────────────┴─────────────┘
                                                  │
                                    ┌─────────────▼─────────────┐
                                    │  INSERT/UPDATE Database   │
                                    │  (drive_document_repository)│
                                    └─────────────┬─────────────┘
                                                  │
                                    ┌─────────────▼─────────────┐
                                    │  Log Access Attempt       │
                                    │  (drive_access_log)       │
                                    └─────────────┬─────────────┘
                                                  │
                                    ┌─────────────▼─────────────┐
                                    │  Format & Return Response │
                                    └─────────────────────────────┘
```

## Node Configuration

### Trigger
- **Type:** Webhook (POST)
- **Path:** `/drive-document-repo`
- **Response Mode:** responseNode

### Google Drive Nodes
- **Credential:** `jlnNh8eZIxWdsvDS`
- **TypeVersion:** 3
- **Operations:**
  - `fileFolder.search` (list folder contents)
  - `file.download` (download files)

### Text Extraction
| MIME Type | Method | Node |
|-----------|--------|------|
| `application/pdf` | Direct extraction | `readPDF` v1 |
| `application/vnd.google-apps.document` | Export as text | Google Drive download with conversion |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Convert to Google Doc first | HTTP Request + Google Drive |
| `text/plain` | Direct read | `extractFromFile` v1.1 |
| `image/*` | AI Vision | OpenAI GPT-4o |

### Database
- **Credential:** `NI3jbq1U8xPst3j3` (PostgreSQL)
- **Tables:** `drive_document_repository`, `drive_access_log`
- **Functions:** `check_file_needs_processing()`, `search_drive_documents()`

## Request/Response Formats

### List Request
```json
{
  "operation": "list"
}
```

### Search Request
```json
{
  "operation": "search",
  "query": "vacation policy",
  "limit": 10
}
```

### Sync Request
```json
{
  "operation": "sync"
}
```

### Get Request
```json
{
  "operation": "get",
  "file_id": "drive-file-id-here"
}
```

### Analyze Request
```json
{
  "operation": "analyze",
  "file_id": "image-file-id-here"
}
```

## Error Handling

- Invalid operation → Return error with available operations
- File not found → Return 404-style error
- Extraction failed → Log error, mark as FAILED, continue with other files
- Database error → Return error, log access attempt
