# Split In Batches Node Reference (Loop)

> **Node Type**: `n8n-nodes-base.splitInBatches`
> **Latest TypeVersion**: 3
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Split In Batches node (also called Loop) processes items in configurable batch sizes. Essential for rate-limited APIs, memory management, and sequential processing.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batchSize` | number | 1 | Items per batch |
| `options.reset` | boolean | false | Reset batch counter |

---

## Outputs

| Output | Index | Description |
|--------|-------|-------------|
| Done | 0 | Fires after all batches processed |
| Loop | 1 | Fires for each batch |

---

## Basic Configuration

### Process One at a Time
```json
{
  "name": "Loop Over Items",
  "type": "n8n-nodes-base.splitInBatches",
  "typeVersion": 3,
  "parameters": {
    "batchSize": 1,
    "options": {}
  }
}
```

### Process in Batches
```json
{
  "parameters": {
    "batchSize": 10,
    "options": {}
  }
}
```

---

## Connection Structure

The Loop node has TWO outputs that must be wired correctly:

```
                    ┌──────────────────────────────────┐
Input ───────►  Loop Over Items                        │
                    │                                  │
                    ├─► [0] Done ───► Continue After   │
                    │                                  │
                    └─► [1] Loop ───► Process Item ────┘
                                          │
                                          └──── (connects back to Loop)
```

### Correct Connection JSON
```json
{
  "connections": {
    "Loop Over Items": {
      "main": [
        [
          {
            "node": "Continue After Loop",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Process Item",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Process Item": {
      "main": [
        [
          {
            "node": "Loop Over Items",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Loop Flow

1. Items enter Loop node
2. First batch goes to Loop output (index 1)
3. Process nodes execute
4. Items return to Loop node
5. Next batch goes to Loop output
6. After all batches: Done output (index 0) fires

---

## Accessing Batch Data

Within the loop, access batch items:

```javascript
// All items in current batch
$input.all()

// First item in batch
$input.first()

// Current batch index
$runIndex
```

---

## Common Patterns

### Rate-Limited API Calls
```json
{
  "nodes": [
    {
      "name": "Loop Over Items",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3,
      "parameters": {
        "batchSize": 1,
        "options": {}
      }
    },
    {
      "name": "API Call",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.example.com/endpoint",
        "method": "POST"
      }
    },
    {
      "name": "Wait",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 1,
        "unit": "seconds"
      }
    }
  ],
  "connections": {
    "Loop Over Items": {
      "main": [
        [{ "node": "Done Processing", "type": "main", "index": 0 }],
        [{ "node": "API Call", "type": "main", "index": 0 }]
      ]
    },
    "API Call": {
      "main": [
        [{ "node": "Wait", "type": "main", "index": 0 }]
      ]
    },
    "Wait": {
      "main": [
        [{ "node": "Loop Over Items", "type": "main", "index": 0 }]
      ]
    }
  }
}
```

### Batch Database Inserts
```json
{
  "nodes": [
    {
      "name": "Loop Over Items",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3,
      "parameters": {
        "batchSize": 100,
        "options": {}
      }
    },
    {
      "name": "Postgres Insert",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "insert",
        "options": {
          "queryBatching": "transaction"
        }
      }
    }
  ]
}
```

### Conditional Loop Exit
Use IF node to check conditions and optionally skip remaining batches:

```json
{
  "nodes": [
    {
      "name": "Loop",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3,
      "parameters": {
        "batchSize": 1
      }
    },
    {
      "name": "Check Condition",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "options": {
            "conditions": [
              {
                "leftValue": "={{ $json.shouldStop }}",
                "rightValue": true,
                "operator": { "type": "boolean", "operation": "true" }
              }
            ]
          }
        }
      }
    }
  ]
}
```

---

## Reset Option

The `reset` option clears the batch counter. Use when:
- Re-entering loop from outside
- Reprocessing items after error
- Multiple independent loops

```json
{
  "parameters": {
    "batchSize": 10,
    "options": {
      "reset": true
    }
  }
}
```

---

## Memory Considerations

| Scenario | Batch Size | Notes |
|----------|-----------|-------|
| Large payloads | 1-10 | Prevent memory overflow |
| Rate-limited APIs | 1 | Add Wait node |
| Database ops | 50-100 | Balance speed/memory |
| Light processing | 100+ | Max throughput |

---

## Loop with Aggregation

To collect results from all iterations:

```json
{
  "nodes": [
    {
      "name": "Loop",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3,
      "parameters": { "batchSize": 1 }
    },
    {
      "name": "Process",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "return { json: { result: 'processed' } };"
      }
    },
    {
      "name": "Aggregate Results",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "mode": "runOnceForAllItems",
        "jsCode": "// All processed items arrive here\nreturn $input.all();"
      }
    }
  ],
  "connections": {
    "Loop": {
      "main": [
        [{ "node": "Aggregate Results", "type": "main", "index": 0 }],
        [{ "node": "Process", "type": "main", "index": 0 }]
      ]
    },
    "Process": {
      "main": [
        [{ "node": "Loop", "type": "main", "index": 0 }]
      ]
    }
  }
}
```

---

## Anti-Patterns (AVOID)

### 1. Missing Loop-Back Connection
```json
// WRONG - Process doesn't connect back to Loop
"connections": {
  "Loop": {
    "main": [
      [{ "node": "Done", "type": "main", "index": 0 }],
      [{ "node": "Process", "type": "main", "index": 0 }]
    ]
  },
  "Process": {
    "main": [
      [{ "node": "Next Node", "type": "main", "index": 0 }]  // Should go back to Loop!
    ]
  }
}
```

### 2. Infinite Loop
```json
// WRONG - Items keep accumulating
// Make sure to NOT add items inside the loop that feed back to it
```

### 3. Wrong Output Index
```json
// WRONG - Using Done output for loop items
"connections": {
  "Loop": {
    "main": [
      [{ "node": "Process", "type": "main", "index": 0 }],  // This is Done output!
      [{ "node": "Done", "type": "main", "index": 0 }]
    ]
  }
}

// CORRECT - Done is index 0, Loop is index 1
"connections": {
  "Loop": {
    "main": [
      [{ "node": "Done", "type": "main", "index": 0 }],    // Done output
      [{ "node": "Process", "type": "main", "index": 0 }]  // Loop output
    ]
  }
}
```

---

## Validation Checklist

- [ ] Using typeVersion 3
- [ ] Batch size appropriate for use case
- [ ] Done output (index 0) connected to post-loop node
- [ ] Loop output (index 1) connected to processing nodes
- [ ] Loop-back connection exists from last processing node to Loop
- [ ] Reset option set if needed for re-entry
- [ ] Wait node added if API rate limits apply
