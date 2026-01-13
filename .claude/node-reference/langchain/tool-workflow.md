# Tool Workflow Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.toolWorkflow`
> **Latest TypeVersion**: 2.2
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Packages any n8n workflow as a tool for AI agents. Executes a sub-workflow and extracts response from the last node.

**AI Tool Capable**: Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`

---

## Core Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | v≤2.1 only | Function name (letters, numbers, underscores) |
| `description` | string | Yes | Tool description for AI agent context |
| `source` | options | Yes | `database` or `parameter` |
| `workflowId` | WorkflowSelector | source=database | Select workflow from database |
| `workflowInputs` | ResourceMapper | source=database | Map inputs to sub-workflow |
| `workflowJson` | json | source=parameter | Inline workflow JSON |

---

## Reference Configuration

### From Database
```json
{
  "name": "Call Sub-Workflow",
  "type": "@n8n/n8n-nodes-langchain.toolWorkflow",
  "typeVersion": 2.2,
  "parameters": {
    "description": "Fetches customer data from the database and returns formatted results",
    "source": "database",
    "workflowId": {
      "mode": "list",
      "value": "workflow-id-here"
    },
    "workflowInputs": {
      "mappingMode": "defineBelow",
      "value": {
        "customerId": "={{ $json.customer_id }}"
      }
    }
  }
}
```

---

## Connection

- **Output Type**: `ai_tool`
- **Connect To**: AI Agent node
- **Required**: Must be connected to AI agent

---

## Requirements

1. **Sub-workflow Trigger**: Must start with "Execute Workflow Trigger" node
2. **Response Extraction**: Tool extracts output from last node in sub-workflow
3. **Environment Variable**: `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`
4. **AI Agent Connection**: Cannot function standalone

---

## Anti-Patterns

| Issue | Cause | Fix |
|-------|-------|-----|
| Execution failure | Missing Execute Workflow trigger | Add trigger to sub-workflow |
| Parameter errors | Mismatched input names | Align input mapping with trigger |
| Tool won't execute | Missing env var | Set `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true` |
