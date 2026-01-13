# Switch Node Reference (Route)

> **Node Type**: `n8n-nodes-base.switch`
> **Latest TypeVersion**: 3.4
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Switch node (also called Route) routes items to different outputs based on conditions or expressions. Essential for branching workflow logic.

---

## Modes

| Mode | Description |
|------|-------------|
| `rules` | Condition-based routing with filter rules |
| `expression` | Expression-based routing (returns output index) |

---

## Rules Mode

### Basic Configuration
```json
{
  "name": "Route by Status",
  "type": "n8n-nodes-base.switch",
  "typeVersion": 3.4,
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "condition-uuid-1",
                  "leftValue": "={{ $json.status }}",
                  "rightValue": "active",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Active"
        },
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "condition-uuid-2",
                  "leftValue": "={{ $json.status }}",
                  "rightValue": "pending",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Pending"
        }
      ]
    },
    "options": {
      "fallbackOutput": "extra"
    }
  }
}
```

### Multiple Conditions (AND)
```json
{
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "cond-1",
                  "leftValue": "={{ $json.status }}",
                  "rightValue": "active",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                },
                {
                  "id": "cond-2",
                  "leftValue": "={{ $json.priority }}",
                  "rightValue": "high",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Active High Priority"
        }
      ]
    }
  }
}
```

### Multiple Conditions (OR)
```json
{
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "or",
              "conditions": [
                {
                  "id": "cond-1",
                  "leftValue": "={{ $json.type }}",
                  "rightValue": "urgent",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                },
                {
                  "id": "cond-2",
                  "leftValue": "={{ $json.priority }}",
                  "rightValue": 1,
                  "operator": {
                    "type": "number",
                    "operation": "equals"
                  }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "High Priority"
        }
      ]
    }
  }
}
```

---

## Expression Mode

Expression mode evaluates an expression that returns the output index (0-based).

### Basic Expression
```json
{
  "parameters": {
    "mode": "expression",
    "output": "={{ $json.outputIndex }}"
  }
}
```

### Conditional Expression
```json
{
  "parameters": {
    "mode": "expression",
    "output": "={{ $json.status === 'active' ? 0 : ($json.status === 'pending' ? 1 : 2) }}"
  }
}
```

### Mapping Values to Outputs
```json
{
  "parameters": {
    "mode": "expression",
    "output": "={{ {'success': 0, 'warning': 1, 'error': 2}[$json.level] ?? 3 }}"
  }
}
```

---

## Condition Operators

### String Operators
| Operation | Description |
|-----------|-------------|
| `equals` | Exact match |
| `notEquals` | Not equal |
| `contains` | Contains substring |
| `notContains` | Does not contain |
| `startsWith` | Starts with |
| `endsWith` | Ends with |
| `regex` | Matches regex pattern |
| `notRegex` | Does not match regex |
| `empty` | Is empty |
| `notEmpty` | Is not empty |

### Number Operators
| Operation | Description |
|-----------|-------------|
| `equals` | Equal to |
| `notEquals` | Not equal |
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |

### Boolean Operators
| Operation | Description |
|-----------|-------------|
| `true` | Is true |
| `false` | Is false |

### Array Operators
| Operation | Description |
|-----------|-------------|
| `contains` | Array contains value |
| `notContains` | Array does not contain |
| `lengthEquals` | Array length equals |
| `lengthGt` | Array length greater than |
| `lengthLt` | Array length less than |
| `empty` | Array is empty |
| `notEmpty` | Array is not empty |

### Object Operators
| Operation | Description |
|-----------|-------------|
| `empty` | Object is empty |
| `notEmpty` | Object is not empty |

### Date Operators
| Operation | Description |
|-----------|-------------|
| `after` | After date |
| `before` | Before date |

---

## Options

| Option | Description |
|--------|-------------|
| `fallbackOutput` | Where unmatched items go: `none` (discard), `extra` (separate output) |
| `ignoreCase` | Case-insensitive string comparisons |
| `looseTypeValidation` | Allow type coercion in comparisons |
| `allMatchingOutputs` | Send item to ALL matching outputs (not just first) |

### Fallback Output
```json
{
  "parameters": {
    "mode": "rules",
    "rules": { "values": [...] },
    "options": {
      "fallbackOutput": "extra"
    }
  }
}
```

### All Matching Outputs
```json
{
  "parameters": {
    "mode": "rules",
    "rules": { "values": [...] },
    "options": {
      "allMatchingOutputs": true
    }
  }
}
```

---

## Common Patterns

### Route by Type
```json
{
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "type-email",
                  "leftValue": "={{ $json.type }}",
                  "rightValue": "email",
                  "operator": { "type": "string", "operation": "equals" }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Email"
        },
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "type-slack",
                  "leftValue": "={{ $json.type }}",
                  "rightValue": "slack",
                  "operator": { "type": "string", "operation": "equals" }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Slack"
        }
      ]
    },
    "options": {
      "fallbackOutput": "extra"
    }
  }
}
```

### Route by Numeric Range
```json
{
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "score-high",
                  "leftValue": "={{ $json.score }}",
                  "rightValue": 80,
                  "operator": { "type": "number", "operation": "gte" }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "High Score"
        },
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "score-medium",
                  "leftValue": "={{ $json.score }}",
                  "rightValue": 50,
                  "operator": { "type": "number", "operation": "gte" }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Medium Score"
        }
      ]
    },
    "options": {
      "fallbackOutput": "extra"
    }
  }
}
```

### Route by Field Existence
```json
{
  "parameters": {
    "mode": "rules",
    "rules": {
      "values": [
        {
          "conditions": {
            "options": {
              "combinator": "and",
              "conditions": [
                {
                  "id": "has-email",
                  "leftValue": "={{ $json.email }}",
                  "rightValue": "",
                  "operator": { "type": "string", "operation": "notEmpty" }
                }
              ]
            }
          },
          "renameOutput": true,
          "outputKey": "Has Email"
        }
      ]
    },
    "options": {
      "fallbackOutput": "extra"
    }
  }
}
```

---

## Output Naming

When `renameOutput: true`, use `outputKey` to name the output:

```json
{
  "renameOutput": true,
  "outputKey": "Custom Name"
}
```

This helps identify outputs in the workflow editor.

---

## Connection Structure

Switch node outputs connect by index:

```json
{
  "connections": {
    "Switch": {
      "main": [
        [
          { "node": "Process Active", "type": "main", "index": 0 }
        ],
        [
          { "node": "Process Pending", "type": "main", "index": 0 }
        ],
        [
          { "node": "Process Other", "type": "main", "index": 0 }
        ]
      ]
    }
  }
}
```

---

## Anti-Patterns (AVOID)

### 1. Complex Logic in Switch
```json
// WRONG - Use Code node for complex logic
{
  "conditions": [
    { "leftValue": "={{ $json.a && $json.b || ($json.c > 5 && $json.d.includes('x')) }}" }
  ]
}

// CORRECT - Break into multiple conditions or use Code node
```

### 2. Missing Fallback
```json
// WRONG - Items may be lost
{
  "options": {
    "fallbackOutput": "none"
  }
}

// CORRECT - Use fallback for unmatched
{
  "options": {
    "fallbackOutput": "extra"
  }
}
```

---

## Validation Checklist

- [ ] Using typeVersion 3.4
- [ ] Mode specified (rules or expression)
- [ ] Each rule has unique condition IDs
- [ ] Combinator set (and/or) for multiple conditions
- [ ] Fallback output configured
- [ ] Output keys descriptive (if using renameOutput)
- [ ] Expression returns valid output index (expression mode)
