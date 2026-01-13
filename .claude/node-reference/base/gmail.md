# Gmail Node Reference

> **Node Type**: `n8n-nodes-base.gmail`
> **Latest TypeVersion**: 2.2
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Gmail node integrates with Google's Gmail API to send, receive, and manage emails. Supports both OAuth2 and Service Account authentication.

---

## Resources & Operations

### Message Resource
| Operation | Description |
|-----------|-------------|
| `send` | Send an email |
| `sendAndWait` | Send email and wait for response (approval/reply) |
| `reply` | Reply to an email |
| `get` | Get a single email |
| `getAll` | Get multiple emails |
| `delete` | Delete an email |
| `markAsRead` | Mark email as read |
| `markAsUnread` | Mark email as unread |
| `addLabels` | Add labels to email |
| `removeLabels` | Remove labels from email |

### Draft Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a draft |
| `get` | Get a draft |
| `getAll` | Get all drafts |
| `delete` | Delete a draft |

### Label Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a label |
| `get` | Get a label |
| `getAll` | Get all labels |
| `delete` | Delete a label |

### Thread Resource
| Operation | Description |
|-----------|-------------|
| `get` | Get a thread |
| `getAll` | Get all threads |
| `delete` | Delete a thread |
| `reply` | Reply to a thread |
| `trash` | Trash a thread |
| `untrash` | Untrash a thread |
| `addLabels` | Add labels to thread |
| `removeLabels` | Remove labels from thread |

---

## Authentication

| Credential Type | Description |
|-----------------|-------------|
| `gmailOAuth2` | OAuth2 (recommended for user accounts) |
| `googleApi` | Service Account (for workspace/domain-wide) |

---

## Send Email Configuration

### Basic Template
```json
{
  "name": "Send Email",
  "type": "n8n-nodes-base.gmail",
  "typeVersion": 2.2,
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "={{ $json.recipient }}",
    "subject": "={{ $json.subject }}",
    "emailType": "text",
    "message": "={{ $json.body }}"
  },
  "credentials": {
    "gmailOAuth2": {
      "id": "your-credential-id",
      "name": "Gmail OAuth2"
    }
  }
}
```

### HTML Email Template
```json
{
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "recipient@example.com",
    "subject": "HTML Email",
    "emailType": "html",
    "message": "<h1>Hello</h1><p>This is an HTML email.</p>",
    "options": {
      "appendAttributionToBody": false
    }
  }
}
```

### With Attachments
```json
{
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "recipient@example.com",
    "subject": "Email with Attachment",
    "emailType": "text",
    "message": "Please see attached.",
    "options": {
      "attachmentsUi": {
        "attachmentsBinary": [
          {
            "property": "data"
          }
        ]
      }
    }
  }
}
```

---

## SendAndWait Configuration

The `sendAndWait` operation pauses workflow execution until recipient responds.

### Approval Request
```json
{
  "parameters": {
    "resource": "message",
    "operation": "sendAndWait",
    "sendTo": "approver@example.com",
    "subject": "Approval Required",
    "emailType": "text",
    "message": "Please approve this request.",
    "responseType": "approval",
    "options": {
      "approvalOptions": {
        "values": {
          "approveLabel": "Approve",
          "disapproveLabel": "Reject"
        }
      }
    }
  }
}
```

### Free Text Response
```json
{
  "parameters": {
    "resource": "message",
    "operation": "sendAndWait",
    "sendTo": "user@example.com",
    "subject": "Input Required",
    "emailType": "text",
    "message": "Please provide your feedback.",
    "responseType": "freeText"
  }
}
```

### Custom Form Response
```json
{
  "parameters": {
    "resource": "message",
    "operation": "sendAndWait",
    "sendTo": "user@example.com",
    "subject": "Survey",
    "emailType": "text",
    "message": "Please fill out the form.",
    "responseType": "customForm",
    "defineForm": {
      "formFields": [
        {
          "fieldLabel": "Rating",
          "fieldType": "number",
          "requiredField": true
        },
        {
          "fieldLabel": "Comments",
          "fieldType": "text",
          "requiredField": false
        }
      ]
    }
  }
}
```

---

## Get Emails Configuration

### Get All Emails (with filters)
```json
{
  "parameters": {
    "resource": "message",
    "operation": "getAll",
    "returnAll": false,
    "limit": 50,
    "filters": {
      "includeSpamTrash": false,
      "labelIds": ["INBOX"],
      "q": "is:unread"
    }
  }
}
```

### Get Single Email
```json
{
  "parameters": {
    "resource": "message",
    "operation": "get",
    "messageId": {
      "__rl": true,
      "value": "={{ $json.messageId }}",
      "mode": "id"
    },
    "options": {
      "dataPropertyAttachmentsPrefixName": "attachment_"
    }
  }
}
```

---

## Options Reference

### Send Options
| Option | Type | Description |
|--------|------|-------------|
| `ccList` | string | CC recipients |
| `bccList` | string | BCC recipients |
| `replyTo` | string | Reply-to address |
| `senderName` | string | Display name for sender |
| `appendAttributionToBody` | boolean | Add n8n attribution |
| `attachmentsUi` | object | Attachment configuration |

### Get Options
| Option | Type | Description |
|--------|------|-------------|
| `dataPropertyAttachmentsPrefixName` | string | Binary property prefix for attachments |

---

## Query Filter Syntax

Gmail uses a query syntax for filtering emails:

| Filter | Example | Description |
|--------|---------|-------------|
| `is:unread` | `is:unread` | Unread emails |
| `from:` | `from:sender@example.com` | From specific sender |
| `to:` | `to:recipient@example.com` | To specific recipient |
| `subject:` | `subject:invoice` | Subject contains word |
| `after:` | `after:2024/01/01` | After date |
| `before:` | `before:2024/12/31` | Before date |
| `has:attachment` | `has:attachment` | Has attachments |
| `label:` | `label:important` | Has specific label |

Combine filters: `is:unread from:boss@company.com after:2024/01/01`

---

## Common Patterns

### Reply to Email
```json
{
  "parameters": {
    "resource": "message",
    "operation": "reply",
    "messageId": {
      "__rl": true,
      "value": "={{ $json.id }}",
      "mode": "id"
    },
    "message": "Thank you for your email."
  }
}
```

### Manage Labels
```json
{
  "parameters": {
    "resource": "message",
    "operation": "addLabels",
    "messageId": {
      "__rl": true,
      "value": "={{ $json.id }}",
      "mode": "id"
    },
    "labelIds": ["Label_1", "Label_2"]
  }
}
```

---

## Related Nodes

- **Gmail Tool** (`n8n-nodes-base.gmailTool`) - AI Agent integration variant
- **IMAP Email** - For non-Gmail email providers

---

## Validation Checklist

- [ ] Using typeVersion 2.2
- [ ] Credentials configured (OAuth2 or Service Account)
- [ ] Resource and operation specified
- [ ] MessageId uses ResourceLocator format for get/reply operations
- [ ] Query syntax valid for getAll filters
