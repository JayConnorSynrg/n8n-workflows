# Google Drive Node Reference

> **Node Type**: `n8n-nodes-base.googleDrive`
> **Latest TypeVersion**: 3
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Google Drive node integrates with Google Drive API for file and folder management. Supports upload, download, copy, move, delete, share, and search operations.

---

## Resources & Operations

### Drive Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a new shared drive |
| `delete` | Delete a shared drive |
| `get` | Get a shared drive |
| `getAll` | Get all shared drives |
| `update` | Update a shared drive |

### File Resource
| Operation | Description |
|-----------|-------------|
| `copy` | Copy a file |
| `createFromText` | Create file from text content |
| `delete` | Delete a file |
| `download` | Download a file |
| `move` | Move a file to different folder |
| `share` | Share a file |
| `update` | Update file content/metadata |
| `upload` | Upload a file |

### Folder Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a folder |
| `delete` | Delete a folder |
| `share` | Share a folder |

### File/Folder Resource (Combined)
| Operation | Description |
|-----------|-------------|
| `search` | Search for files/folders |

---

## Authentication

| Credential Type | Description |
|-----------------|-------------|
| `googleDriveOAuth2Api` | OAuth2 (recommended) |
| `serviceAccount` | Service Account |

---

## File Operations

### Upload File
```json
{
  "name": "Upload to Drive",
  "type": "n8n-nodes-base.googleDrive",
  "typeVersion": 3,
  "parameters": {
    "resource": "file",
    "operation": "upload",
    "name": "={{ $json.fileName }}",
    "folderId": {
      "__rl": true,
      "value": "root",
      "mode": "list",
      "cachedResultName": "/ (Root folder)"
    },
    "options": {}
  },
  "credentials": {
    "googleDriveOAuth2Api": {
      "id": "your-credential-id",
      "name": "Google Drive OAuth2"
    }
  }
}
```

### Upload with Binary Data
```json
{
  "parameters": {
    "resource": "file",
    "operation": "upload",
    "name": "uploaded-file.pdf",
    "folderId": {
      "__rl": true,
      "value": "folder-id-here",
      "mode": "id"
    },
    "options": {
      "originalFilename": "my-document.pdf"
    }
  }
}
```

### Download File
```json
{
  "parameters": {
    "resource": "file",
    "operation": "download",
    "fileId": {
      "__rl": true,
      "value": "={{ $json.fileId }}",
      "mode": "id"
    },
    "options": {
      "googleFileConversion": {
        "docsToFormat": "application/pdf"
      }
    }
  }
}
```

### Create File from Text
```json
{
  "parameters": {
    "resource": "file",
    "operation": "createFromText",
    "name": "notes.txt",
    "content": "={{ $json.textContent }}",
    "folderId": {
      "__rl": true,
      "value": "root",
      "mode": "list"
    },
    "options": {}
  }
}
```

---

## Folder Operations

### Create Folder
```json
{
  "parameters": {
    "resource": "folder",
    "operation": "create",
    "name": "={{ $json.folderName }}",
    "folderLocation": {
      "__rl": true,
      "value": "root",
      "mode": "list"
    },
    "options": {}
  }
}
```

### Create Folder in Shared Drive
```json
{
  "parameters": {
    "resource": "folder",
    "operation": "create",
    "name": "New Project Folder",
    "folderLocation": {
      "__rl": true,
      "value": "shared-drive-id",
      "mode": "id"
    },
    "options": {
      "driveId": {
        "__rl": true,
        "value": "shared-drive-id",
        "mode": "id"
      }
    }
  }
}
```

---

## Search Operations

### Search Files
```json
{
  "parameters": {
    "resource": "fileFolder",
    "operation": "search",
    "returnAll": false,
    "limit": 50,
    "filter": {
      "folderId": {
        "__rl": true,
        "value": "root",
        "mode": "list"
      }
    },
    "options": {
      "fields": ["id", "name", "mimeType", "webViewLink", "createdTime"]
    }
  }
}
```

### Search with Query Filter
```json
{
  "parameters": {
    "resource": "fileFolder",
    "operation": "search",
    "returnAll": false,
    "limit": 20,
    "queryString": "name contains 'report' and mimeType='application/pdf'",
    "options": {}
  }
}
```

---

## Share Operations

### Share File
```json
{
  "parameters": {
    "resource": "file",
    "operation": "share",
    "fileId": {
      "__rl": true,
      "value": "={{ $json.fileId }}",
      "mode": "id"
    },
    "permissions": {
      "role": "reader",
      "type": "user"
    },
    "options": {
      "emailAddress": "user@example.com",
      "sendNotificationEmail": true,
      "emailMessage": "Here's the file you requested."
    }
  }
}
```

### Share Folder
```json
{
  "parameters": {
    "resource": "folder",
    "operation": "share",
    "folderId": {
      "__rl": true,
      "value": "folder-id-here",
      "mode": "id"
    },
    "permissions": {
      "role": "writer",
      "type": "user"
    },
    "options": {
      "emailAddress": "collaborator@example.com"
    }
  }
}
```

---

## Move & Copy Operations

### Move File
```json
{
  "parameters": {
    "resource": "file",
    "operation": "move",
    "fileId": {
      "__rl": true,
      "value": "={{ $json.fileId }}",
      "mode": "id"
    },
    "folderId": {
      "__rl": true,
      "value": "destination-folder-id",
      "mode": "id"
    }
  }
}
```

### Copy File
```json
{
  "parameters": {
    "resource": "file",
    "operation": "copy",
    "fileId": {
      "__rl": true,
      "value": "={{ $json.fileId }}",
      "mode": "id"
    },
    "options": {
      "name": "Copy of {{ $json.fileName }}"
    }
  }
}
```

---

## ResourceLocator Format

Google Drive uses ResourceLocator for file/folder IDs:

### By ID
```json
{
  "fileId": {
    "__rl": true,
    "value": "1abc123def456",
    "mode": "id"
  }
}
```

### From List (UI selection)
```json
{
  "folderId": {
    "__rl": true,
    "value": "root",
    "mode": "list",
    "cachedResultName": "/ (Root folder)"
  }
}
```

### From URL
```json
{
  "fileId": {
    "__rl": true,
    "value": "https://drive.google.com/file/d/1abc123def456/view",
    "mode": "url"
  }
}
```

---

## Query Syntax for Search

| Query | Description |
|-------|-------------|
| `name = 'filename'` | Exact name match |
| `name contains 'text'` | Name contains text |
| `mimeType = 'application/pdf'` | File type filter |
| `'folder-id' in parents` | Files in specific folder |
| `trashed = false` | Exclude trashed files |
| `modifiedTime > '2024-01-01'` | Modified after date |

Combine with `and`/`or`: `name contains 'report' and mimeType='application/pdf'`

---

## Common MIME Types

| Type | MIME Type |
|------|-----------|
| Google Doc | `application/vnd.google-apps.document` |
| Google Sheet | `application/vnd.google-apps.spreadsheet` |
| Google Slides | `application/vnd.google-apps.presentation` |
| PDF | `application/pdf` |
| Plain Text | `text/plain` |
| Image (PNG) | `image/png` |
| Image (JPEG) | `image/jpeg` |

---

## Permission Roles

| Role | Description |
|------|-------------|
| `reader` | Can view |
| `commenter` | Can view and comment |
| `writer` | Can edit |
| `fileOrganizer` | Can manage (folders only) |
| `organizer` | Can manage members (shared drives) |
| `owner` | Full control |

---

## Validation Checklist

- [ ] Using typeVersion 3
- [ ] Credentials configured (OAuth2 or Service Account)
- [ ] Resource and operation specified
- [ ] File/Folder IDs use ResourceLocator format
- [ ] Binary data property set for upload (if not auto-detected)
- [ ] Shared drive ID specified for shared drive operations
