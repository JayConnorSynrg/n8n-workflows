# Microsoft Teams Node Reference

> **Node Type**: `n8n-nodes-base.microsoftTeams`
> **Latest TypeVersion**: 2
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Microsoft Teams node integrates with Microsoft Graph API for Teams messaging, channel management, and task operations.

---

## Resources & Operations

### Channel Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a channel in a team |
| `delete` | Delete a channel |
| `get` | Get a channel |
| `getAll` | Get all channels in a team |
| `update` | Update a channel |

### Channel Message Resource
| Operation | Description |
|-----------|-------------|
| `create` | Post a message to a channel |
| `getAll` | Get all messages in a channel |

### Chat Message Resource
| Operation | Description |
|-----------|-------------|
| `create` | Send a chat message |
| `get` | Get a chat message |
| `getAll` | Get all messages in a chat |
| `sendAndWait` | Send message and wait for response |

### Task Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a task in Planner |
| `delete` | Delete a task |
| `get` | Get a task |
| `getAll` | Get all tasks |
| `update` | Update a task |

---

## Authentication

| Credential Type | Description |
|-----------------|-------------|
| `microsoftTeamsOAuth2Api` | OAuth2 (recommended) |

---

## Channel Message Operations

### Post to Channel
```json
{
  "name": "Post to Teams Channel",
  "type": "n8n-nodes-base.microsoftTeams",
  "typeVersion": 2,
  "parameters": {
    "resource": "channelMessage",
    "operation": "create",
    "teamId": {
      "__rl": true,
      "value": "={{ $json.teamId }}",
      "mode": "id"
    },
    "channelId": {
      "__rl": true,
      "value": "={{ $json.channelId }}",
      "mode": "id"
    },
    "contentType": "text",
    "message": "={{ $json.message }}"
  },
  "credentials": {
    "microsoftTeamsOAuth2Api": {
      "id": "your-credential-id",
      "name": "Microsoft Teams OAuth2"
    }
  }
}
```

### Post HTML Message
```json
{
  "parameters": {
    "resource": "channelMessage",
    "operation": "create",
    "teamId": {
      "__rl": true,
      "value": "team-guid-here",
      "mode": "id"
    },
    "channelId": {
      "__rl": true,
      "value": "channel-id-here",
      "mode": "id"
    },
    "contentType": "html",
    "message": "<h1>Alert</h1><p>This is an <strong>important</strong> message.</p>"
  }
}
```

---

## Chat Message Operations

### Send Direct Chat Message
```json
{
  "parameters": {
    "resource": "chatMessage",
    "operation": "create",
    "chatId": {
      "__rl": true,
      "value": "={{ $json.chatId }}",
      "mode": "id"
    },
    "contentType": "text",
    "message": "Hello! This is a direct message."
  }
}
```

### Send and Wait for Response
```json
{
  "parameters": {
    "resource": "chatMessage",
    "operation": "sendAndWait",
    "chatId": {
      "__rl": true,
      "value": "chat-id-here",
      "mode": "id"
    },
    "contentType": "text",
    "message": "Do you approve this request?",
    "responseType": "approval",
    "options": {
      "approvalOptions": {
        "values": {
          "approveLabel": "Yes",
          "disapproveLabel": "No"
        }
      }
    }
  }
}
```

---

## Channel Operations

### Create Channel
```json
{
  "parameters": {
    "resource": "channel",
    "operation": "create",
    "teamId": {
      "__rl": true,
      "value": "team-guid-here",
      "mode": "id"
    },
    "name": "Project Updates",
    "options": {
      "description": "Channel for project status updates",
      "type": "standard"
    }
  }
}
```

### Get All Channels
```json
{
  "parameters": {
    "resource": "channel",
    "operation": "getAll",
    "teamId": {
      "__rl": true,
      "value": "team-guid-here",
      "mode": "id"
    },
    "returnAll": true
  }
}
```

---

## Task Operations (Planner)

### Create Task
```json
{
  "parameters": {
    "resource": "task",
    "operation": "create",
    "groupId": {
      "__rl": true,
      "value": "group-guid-here",
      "mode": "id"
    },
    "planId": {
      "__rl": true,
      "value": "plan-guid-here",
      "mode": "id"
    },
    "bucketId": {
      "__rl": true,
      "value": "bucket-guid-here",
      "mode": "id"
    },
    "title": "={{ $json.taskTitle }}",
    "options": {
      "dueDateTime": "={{ $json.dueDate }}",
      "percentComplete": 0
    }
  }
}
```

### Update Task
```json
{
  "parameters": {
    "resource": "task",
    "operation": "update",
    "taskId": "task-guid-here",
    "updateFields": {
      "percentComplete": 50,
      "title": "Updated Task Title"
    }
  }
}
```

---

## ResourceLocator Format

Microsoft Teams uses ResourceLocator for team/channel/chat IDs:

### By ID
```json
{
  "teamId": {
    "__rl": true,
    "value": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "mode": "id"
  }
}
```

### From List (UI selection)
```json
{
  "teamId": {
    "__rl": true,
    "value": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "mode": "list",
    "cachedResultName": "My Team"
  }
}
```

---

## SendAndWait Response Types

| Type | Description |
|------|-------------|
| `approval` | Yes/No buttons |
| `freeText` | Open text response |
| `customForm` | Custom form fields |

### Custom Form Example
```json
{
  "parameters": {
    "resource": "chatMessage",
    "operation": "sendAndWait",
    "chatId": {
      "__rl": true,
      "value": "chat-id",
      "mode": "id"
    },
    "message": "Please provide details:",
    "responseType": "customForm",
    "defineForm": {
      "formFields": [
        {
          "fieldLabel": "Priority",
          "fieldType": "dropdown",
          "requiredField": true,
          "fieldOptions": {
            "values": [
              { "option": "High" },
              { "option": "Medium" },
              { "option": "Low" }
            ]
          }
        },
        {
          "fieldLabel": "Notes",
          "fieldType": "text",
          "requiredField": false
        }
      ]
    }
  }
}
```

---

## Common Patterns

### Post Workflow Status to Channel
```json
{
  "parameters": {
    "resource": "channelMessage",
    "operation": "create",
    "teamId": {
      "__rl": true,
      "value": "team-id",
      "mode": "id"
    },
    "channelId": {
      "__rl": true,
      "value": "channel-id",
      "mode": "id"
    },
    "contentType": "html",
    "message": "<b>Workflow Status:</b> {{ $json.status }}<br><br>Processed {{ $json.itemCount }} items at {{ $now.toISO() }}"
  }
}
```

### Get Recent Channel Messages
```json
{
  "parameters": {
    "resource": "channelMessage",
    "operation": "getAll",
    "teamId": {
      "__rl": true,
      "value": "team-id",
      "mode": "id"
    },
    "channelId": {
      "__rl": true,
      "value": "channel-id",
      "mode": "id"
    },
    "returnAll": false,
    "limit": 10
  }
}
```

---

## Channel Types

| Type | Description |
|------|-------------|
| `standard` | Normal channel, visible to all team members |
| `private` | Private channel, limited membership |
| `shared` | Shared channel across teams |

---

## Validation Checklist

- [ ] Using typeVersion 2
- [ ] Credentials configured (OAuth2)
- [ ] Resource and operation specified
- [ ] Team/Channel/Chat IDs use ResourceLocator format
- [ ] Content type set correctly (text or html)
- [ ] For Planner tasks: groupId, planId, and bucketId specified
