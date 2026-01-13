# Chat Trigger Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.chatTrigger`
> **Latest TypeVersion**: 1.4
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Webhook-based trigger for n8n-generated webchat. Supports hosted chat, webhook mode, and n8n Chat integration.

---

## Core Parameters

### Public Access

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `public` | boolean | false | Enable public chat |
| `mode` | options | - | `hostedChat` or `webhook` |
| `authentication` | options | - | `none`, `basicAuth`, `n8nUserAuth` |

### Display (Hosted Chat)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `initialMessages` | string | - | Greeting at chat start |
| `title` | string | "Hi there! 👋" | Header title |
| `subtitle` | string | - | Subheader text |
| `showWelcomeScreen` | boolean | - | Show start button first |
| `inputPlaceholder` | string | "Type your question.." | Input placeholder |

### n8n Chat Integration (v1.2+)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `availableInChat` | boolean | - | Show in n8n Chat |
| `agentName` | string | - | Display name |
| `agentDescription` | string | - | Agent description |

### Session & Response

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loadPreviousSession` | options | `notSupported` | `notSupported`, `memory`, `manually` |
| `responseMode` | options | - | `lastNode`, `responseNode`, `responseNodes`, `streaming` |
| `allowFileUploads` | boolean | false | Enable file uploads |
| `allowedFilesMimeTypes` | string | "*" | Comma-separated MIME types |

---

## Reference Configuration

### Public Hosted Chat
```json
{
  "name": "Chat Trigger",
  "type": "@n8n/n8n-nodes-langchain.chatTrigger",
  "typeVersion": 1.4,
  "webhookId": "unique-id",
  "parameters": {
    "public": true,
    "mode": "hostedChat",
    "authentication": "none",
    "initialMessages": "Hi! How can I help you today?",
    "title": "AI Assistant",
    "responseMode": "lastNode"
  }
}
```

### n8n Chat Integration
```json
{
  "parameters": {
    "availableInChat": true,
    "agentName": "My Agent",
    "agentDescription": "Helpful AI assistant",
    "responseMode": "streaming"
  }
}
```

### Webhook with File Support
```json
{
  "parameters": {
    "public": true,
    "mode": "webhook",
    "allowFileUploads": true,
    "allowedFilesMimeTypes": "image/*, application/pdf",
    "responseMode": "responseNode"
  }
}
```

---

## Critical Rules

1. **Streaming Required for n8n Chat**: When `availableInChat: true`, use `responseMode: "streaming"`
2. **Public Publication**: Chat goes live only after workflow is published
3. **Session Recovery**: Use `loadPreviousSession: "memory"` for conversation continuity
4. **Output Field**: Provides `chatInput` field for downstream AI Agent nodes

---

## TypeVersion History

| Version | Features |
|---------|----------|
| 1.0-1.1 | Basic hostedChat/webhook modes |
| 1.2 | n8n Chat integration, streaming |
| 1.3 | responseNodes mode |
| 1.4 | Current - full feature set |
