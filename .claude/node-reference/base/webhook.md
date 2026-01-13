# Webhook Node Reference

> **Node Type**: `n8n-nodes-base.webhook`
> **Latest TypeVersion**: 2.1
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Webhook node creates an HTTP endpoint that triggers workflow execution when called. Essential for receiving data from external services, APIs, and integrations.

---

## HTTP Methods

| Method | Description |
|--------|-------------|
| `GET` | Retrieve data |
| `POST` | Submit data |
| `PUT` | Update/replace data |
| `PATCH` | Partial update |
| `DELETE` | Remove data |
| `HEAD` | Headers only |

---

## Response Modes

| Mode | Description |
|------|-------------|
| `onReceived` | Respond immediately when webhook is received |
| `lastNode` | Respond with output from last executed node |
| `responseNode` | Use Respond to Webhook node for response |
| `streaming` | Stream response back (v2.1+) |

---

## Basic Configuration

### Simple Webhook
```json
{
  "name": "Webhook",
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 2.1,
  "parameters": {
    "path": "my-webhook",
    "httpMethod": "POST",
    "responseMode": "onReceived",
    "options": {}
  },
  "webhookId": "unique-webhook-id"
}
```

### With Authentication
```json
{
  "parameters": {
    "path": "secure-webhook",
    "httpMethod": "POST",
    "authentication": "headerAuth",
    "responseMode": "onReceived",
    "options": {}
  },
  "credentials": {
    "httpHeaderAuth": {
      "id": "your-credential-id",
      "name": "API Key Auth"
    }
  }
}
```

---

## Authentication Options

| Type | Description |
|------|-------------|
| `none` | No authentication |
| `basicAuth` | HTTP Basic Auth |
| `headerAuth` | Header-based auth (API keys) |
| `jwtAuth` | JWT token validation |

### Basic Auth
```json
{
  "parameters": {
    "authentication": "basicAuth"
  },
  "credentials": {
    "httpBasicAuth": {
      "id": "credential-id",
      "name": "Basic Auth"
    }
  }
}
```

### Header Auth
```json
{
  "parameters": {
    "authentication": "headerAuth"
  },
  "credentials": {
    "httpHeaderAuth": {
      "id": "credential-id",
      "name": "API Key"
    }
  }
}
```

### JWT Auth
```json
{
  "parameters": {
    "authentication": "jwtAuth"
  },
  "credentials": {
    "jwtAuth": {
      "id": "credential-id",
      "name": "JWT Auth"
    }
  }
}
```

---

## Response Mode Configurations

### Immediate Response
```json
{
  "parameters": {
    "responseMode": "onReceived",
    "options": {
      "responseCode": 200,
      "responseData": "firstEntryJson"
    }
  }
}
```

### Response from Last Node
```json
{
  "parameters": {
    "responseMode": "lastNode",
    "options": {
      "responseData": "allEntries"
    }
  }
}
```

### Using Respond to Webhook Node
```json
{
  "parameters": {
    "responseMode": "responseNode",
    "options": {}
  }
}
```

### Streaming Response (v2.1)
```json
{
  "parameters": {
    "responseMode": "streaming",
    "options": {
      "responseContentType": "text/event-stream"
    }
  }
}
```

---

## Response Data Options

| Option | Description |
|--------|-------------|
| `firstEntryJson` | First item's JSON |
| `firstEntryBinary` | First item's binary data |
| `allEntries` | All items as JSON array |
| `noData` | Empty response |

---

## Handling Binary Data

### Receive File Upload
```json
{
  "parameters": {
    "path": "upload",
    "httpMethod": "POST",
    "responseMode": "onReceived",
    "options": {
      "binaryData": true,
      "rawBody": true
    }
  }
}
```

### Return Binary Data
```json
{
  "parameters": {
    "responseMode": "lastNode",
    "options": {
      "responseData": "firstEntryBinary",
      "responseBinaryPropertyName": "data"
    }
  }
}
```

---

## Advanced Options

### Custom Headers
```json
{
  "parameters": {
    "options": {
      "responseHeaders": {
        "entries": [
          {
            "name": "X-Custom-Header",
            "value": "custom-value"
          },
          {
            "name": "Access-Control-Allow-Origin",
            "value": "*"
          }
        ]
      }
    }
  }
}
```

### Custom Response Code
```json
{
  "parameters": {
    "options": {
      "responseCode": 201
    }
  }
}
```

### Raw Body Access
```json
{
  "parameters": {
    "options": {
      "rawBody": true
    }
  }
}
```

### IP Whitelist
```json
{
  "parameters": {
    "options": {
      "allowedOrigins": "192.168.1.0/24,10.0.0.0/8"
    }
  }
}
```

---

## Webhook URL Structure

Production URL:
```
https://your-n8n-instance.com/webhook/my-webhook
```

Test URL (workflow not active):
```
https://your-n8n-instance.com/webhook-test/my-webhook
```

With path parameters:
```
https://your-n8n-instance.com/webhook/users/:userId/orders/:orderId
```

---

## Accessing Webhook Data

### Headers
```javascript
$json.headers['content-type']
$json.headers['authorization']
```

### Query Parameters
```javascript
$json.query.param1
$json.query.param2
```

### Path Parameters (when using :paramName)
```javascript
$json.params.userId
$json.params.orderId
```

### Body
```javascript
$json.body.fieldName
// or directly if body is parsed
$json.fieldName
```

### Method
```javascript
$json.method
```

---

## Common Patterns

### API Endpoint with Validation
```json
{
  "parameters": {
    "path": "api/v1/data",
    "httpMethod": "POST",
    "authentication": "headerAuth",
    "responseMode": "responseNode",
    "options": {
      "responseCode": 200
    }
  }
}
```

### Receive GitHub Webhook
```json
{
  "parameters": {
    "path": "github-events",
    "httpMethod": "POST",
    "authentication": "none",
    "responseMode": "onReceived",
    "options": {
      "rawBody": true
    }
  }
}
```

### Multiple HTTP Methods
For accepting multiple methods, use the Webhook node's `httpMethod` array option or create separate webhooks:

```json
{
  "parameters": {
    "path": "resource",
    "httpMethod": "=GET,POST,PUT,DELETE",
    "responseMode": "responseNode"
  }
}
```

---

## Error Responses

Use Respond to Webhook node for error handling:

```json
{
  "name": "Respond Error",
  "type": "n8n-nodes-base.respondToWebhook",
  "parameters": {
    "respondWith": "json",
    "responseBody": "={{ { error: $json.errorMessage, code: 400 } }}",
    "options": {
      "responseCode": 400
    }
  }
}
```

---

## Test vs Production

| Environment | URL Path | Activation Required |
|-------------|----------|-------------------|
| Test | `/webhook-test/` | No |
| Production | `/webhook/` | Yes |

**Important**: Test webhooks only work when the workflow editor is open. Production webhooks require the workflow to be activated.

---

## TypeVersion 2.1 Features

- Streaming response mode
- Improved binary handling
- Enhanced header management
- Better error responses

---

## Validation Checklist

- [ ] Using typeVersion 2.1
- [ ] Path is unique and descriptive
- [ ] HTTP method appropriate for use case
- [ ] Authentication configured if needed
- [ ] Response mode matches workflow design
- [ ] Response headers include CORS if needed
- [ ] Binary data handling configured for file uploads
- [ ] Error responses handled (use Respond to Webhook node)
