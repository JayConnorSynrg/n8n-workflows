# Execute Workflow Node Reference (Sub-Workflow)

> **Node Type**: `n8n-nodes-base.executeWorkflow`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Execute Workflow node (Sub-Workflow) calls another n8n workflow, enabling modular workflow design. Supports passing data, receiving results, and async execution.

---

## Source Options

| Source | Description |
|--------|-------------|
| `database` | Select workflow from n8n database |
| `parameter` | Workflow ID as parameter |
| `localFile` | Load from local JSON file |
| `url` | Load from remote URL |

---

## Execution Modes

| Mode | Description |
|------|-------------|
| `once` | Execute once with all items |
| `each` | Execute once per input item |

---

## Basic Configuration

### Call Workflow by ID
```json
{
  "name": "Execute Sub-Workflow",
  "type": "n8n-nodes-base.executeWorkflow",
  "typeVersion": 1.3,
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "workflow-id-here",
      "mode": "list",
      "cachedResultName": "My Sub-Workflow"
    },
    "options": {}
  }
}
```

### Call Workflow by Parameter
```json
{
  "parameters": {
    "source": "parameter",
    "workflowId": "={{ $json.targetWorkflowId }}",
    "options": {}
  }
}
```

### Load from URL
```json
{
  "parameters": {
    "source": "url",
    "workflowUrl": "https://example.com/workflow.json",
    "options": {}
  }
}
```

---

## Passing Data to Sub-Workflow

### Using workflowInputs (Resource Mapper)
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "sub-workflow-id",
      "mode": "list"
    },
    "workflowInputs": {
      "mappingMode": "defineBelow",
      "value": {
        "mappings": [
          {
            "parameter": "customerId",
            "value": "={{ $json.customer_id }}"
          },
          {
            "parameter": "orderData",
            "value": "={{ $json.order }}"
          }
        ]
      }
    }
  }
}
```

### Auto-Map Input Data
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "sub-workflow-id",
      "mode": "list"
    },
    "workflowInputs": {
      "mappingMode": "autoMapInputData",
      "value": ""
    }
  }
}
```

---

## Execution Mode Configuration

### Execute Once (All Items)
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "sub-workflow-id",
      "mode": "list"
    },
    "mode": "once",
    "options": {}
  }
}
```

### Execute for Each Item
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "sub-workflow-id",
      "mode": "list"
    },
    "mode": "each",
    "options": {}
  }
}
```

---

## Async Execution

### Fire and Forget
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "sub-workflow-id",
      "mode": "list"
    },
    "options": {
      "waitForSubWorkflow": false
    }
  }
}
```

### Wait for Completion (Default)
```json
{
  "parameters": {
    "options": {
      "waitForSubWorkflow": true
    }
  }
}
```

---

## Sub-Workflow Setup

The sub-workflow needs an Execute Workflow Trigger to receive data:

### Sub-Workflow Trigger
```json
{
  "name": "Execute Workflow Trigger",
  "type": "n8n-nodes-base.executeWorkflowTrigger",
  "typeVersion": 1,
  "parameters": {},
  "position": [0, 0]
}
```

### Accessing Passed Data in Sub-Workflow
```javascript
// Access passed parameters
$json.customerId
$json.orderData

// All input data
$input.all()
```

---

## Return Data from Sub-Workflow

The sub-workflow's final node output becomes the Execute Workflow node's output.

### Sub-Workflow Return Example
```json
{
  "name": "Return Data",
  "type": "n8n-nodes-base.set",
  "parameters": {
    "mode": "manual",
    "duplicateItem": false,
    "assignments": {
      "assignments": [
        {
          "name": "result",
          "value": "={{ $json.processedData }}",
          "type": "string"
        },
        {
          "name": "status",
          "value": "success",
          "type": "string"
        }
      ]
    }
  }
}
```

---

## Common Patterns

### Reusable Data Processor
```json
{
  "parameters": {
    "source": "database",
    "workflowId": {
      "__rl": true,
      "value": "data-processor-workflow-id",
      "mode": "list"
    },
    "workflowInputs": {
      "mappingMode": "defineBelow",
      "value": {
        "mappings": [
          {
            "parameter": "data",
            "value": "={{ $json }}"
          },
          {
            "parameter": "processingType",
            "value": "transform"
          }
        ]
      }
    },
    "mode": "once"
  }
}
```

### Parallel Sub-Workflow Execution
Use Split In Batches with Execute Workflow in "each" mode:

```json
{
  "nodes": [
    {
      "name": "Split Batches",
      "type": "n8n-nodes-base.splitInBatches",
      "parameters": {
        "batchSize": 5
      }
    },
    {
      "name": "Execute Sub-Workflow",
      "type": "n8n-nodes-base.executeWorkflow",
      "parameters": {
        "source": "database",
        "workflowId": { "__rl": true, "value": "sub-id", "mode": "list" },
        "mode": "each"
      }
    }
  ]
}
```

### Dynamic Workflow Selection
```json
{
  "parameters": {
    "source": "parameter",
    "workflowId": "={{ $json.targetWorkflowId || 'default-workflow-id' }}",
    "options": {}
  }
}
```

### Error Handling Sub-Workflow
```json
{
  "nodes": [
    {
      "name": "Execute Main Process",
      "type": "n8n-nodes-base.executeWorkflow",
      "parameters": {
        "source": "database",
        "workflowId": { "__rl": true, "value": "main-process-id", "mode": "list" }
      },
      "onError": "continueErrorOutput"
    },
    {
      "name": "Execute Error Handler",
      "type": "n8n-nodes-base.executeWorkflow",
      "parameters": {
        "source": "database",
        "workflowId": { "__rl": true, "value": "error-handler-id", "mode": "list" }
      }
    }
  ],
  "connections": {
    "Execute Main Process": {
      "main": [
        [{ "node": "Continue", "type": "main", "index": 0 }],
        [{ "node": "Execute Error Handler", "type": "main", "index": 0 }]
      ]
    }
  }
}
```

---

## ResourceLocator Format

Workflow ID uses ResourceLocator:

### From List (UI selection)
```json
{
  "workflowId": {
    "__rl": true,
    "value": "abc123",
    "mode": "list",
    "cachedResultName": "My Workflow Name"
  }
}
```

### By ID
```json
{
  "workflowId": {
    "__rl": true,
    "value": "abc123",
    "mode": "id"
  }
}
```

### From URL
```json
{
  "workflowId": {
    "__rl": true,
    "value": "https://n8n.example.com/workflow/abc123",
    "mode": "url"
  }
}
```

---

## Options Reference

| Option | Type | Description |
|--------|------|-------------|
| `waitForSubWorkflow` | boolean | Wait for sub-workflow to complete |

---

## Anti-Patterns (AVOID)

### 1. Circular Dependencies
```json
// WRONG - Workflow A calls B, B calls A
// This creates infinite recursion
```

### 2. Not Handling Sub-Workflow Errors
```json
// WRONG - No error handling
{
  "onError": "stopWorkflow"  // Default behavior
}

// CORRECT - Handle errors
{
  "onError": "continueErrorOutput"
}
```

### 3. Missing Execute Workflow Trigger
```json
// WRONG - Sub-workflow has no trigger
// The sub-workflow MUST have an Execute Workflow Trigger node
```

---

## Debugging Sub-Workflows

1. **Test Sub-Workflow Independently**: Run sub-workflow with test data first
2. **Check Input Data**: Add Set node before Execute Workflow to log inputs
3. **Verify Trigger**: Ensure sub-workflow has Execute Workflow Trigger
4. **Review Error Output**: Enable `continueErrorOutput` to capture errors

---

## Validation Checklist

- [ ] Using typeVersion 1.3
- [ ] Source specified (database, parameter, localFile, url)
- [ ] Workflow ID uses ResourceLocator format (for database source)
- [ ] workflowInputs configured for passing data
- [ ] Mode appropriate (once vs each)
- [ ] Sub-workflow has Execute Workflow Trigger
- [ ] Error handling configured (onError)
- [ ] waitForSubWorkflow set appropriately
