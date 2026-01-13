# Code Node Reference

> **Node Type**: `n8n-nodes-base.code`
> **Latest TypeVersion**: 2
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Code node executes custom JavaScript or Python code within n8n workflows. Use for complex transformations, data manipulation, or logic that native nodes can't handle.

**Best Practice**: Prefer native nodes (Set, IF, Switch) when possible. Only use Code node for complex transformations.

---

## Languages

| Language | Stability | Description |
|----------|-----------|-------------|
| `javaScript` | Stable | Full JavaScript with n8n helpers |
| `python` | Beta | Python with sandboxed execution |
| `python-native` | Limited | Python with native execution (limited helpers) |

---

## Execution Modes

| Mode | Description |
|------|-------------|
| `runOnceForAllItems` | Code runs once with access to all items |
| `runOnceForEachItem` | Code runs once per item |

---

## JavaScript Configuration

### Run Once for All Items
```json
{
  "name": "Transform Data",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "parameters": {
    "language": "javaScript",
    "mode": "runOnceForAllItems",
    "jsCode": "// Access all items\nconst items = $input.all();\n\n// Transform and return\nreturn items.map(item => ({\n  json: {\n    ...item.json,\n    processed: true,\n    timestamp: new Date().toISOString()\n  }\n}));"
  }
}
```

### Run Once for Each Item
```json
{
  "parameters": {
    "language": "javaScript",
    "mode": "runOnceForEachItem",
    "jsCode": "// Access current item\nconst data = $input.item.json;\n\n// Transform and return\nreturn {\n  json: {\n    original: data,\n    doubled: data.value * 2\n  }\n};"
  }
}
```

---

## JavaScript Helpers

### Input Access
```javascript
// All items (runOnceForAllItems mode)
const items = $input.all();

// First item
const first = $input.first();

// Current item (runOnceForEachItem mode)
const current = $input.item;

// Access by index
const item = $input.item(0);
```

### Node Data Access
```javascript
// Previous node output
const prevData = $('Previous Node').all();

// Specific item from node
const item = $('Node Name').item(0);

// First item from node
const first = $('Node Name').first();
```

### Execution Context
```javascript
// Current execution ID
const execId = $execution.id;

// Workflow info
const workflowId = $workflow.id;
const workflowName = $workflow.name;

// Current node info
const nodeName = $node.name;

// Environment variables
const apiKey = $env.API_KEY;
```

### Date/Time Helpers
```javascript
// Current timestamp
const now = $now;

// Today at midnight
const today = $today;

// Date manipulation (Luxon)
const nextWeek = $now.plus({ days: 7 });
const formatted = $now.toFormat('yyyy-MM-dd');
```

### Utility Functions
```javascript
// Generate UUID
const id = $uuid();

// Get execution resumeUrl (for wait nodes)
const resumeUrl = $execution.resumeUrl;

// Get run index
const runIndex = $runIndex;
```

---

## Python Configuration (Beta)

### Basic Python
```json
{
  "parameters": {
    "language": "python",
    "mode": "runOnceForAllItems",
    "pythonCode": "# Access all items\nitems = _input.all()\n\n# Transform\nresult = []\nfor item in items:\n    result.append({\n        'json': {\n            **item['json'],\n            'processed': True\n        }\n    })\n\nreturn result"
  }
}
```

### Python Helpers (Beta)
```python
# All items
items = _input.all()

# First item
first = _input.first()

# Current item (each mode)
current = _input.item

# Node data
prev_data = _node['Previous Node'].all()

# Environment
api_key = _env['API_KEY']
```

---

## Python Native (Limited)

Python Native has limited helper methods:

```python
# Available helpers (Python Native)
_item   # Current item (each mode)
_items  # All items (all mode)

# NOT available in Python Native:
# _input, _node, _env, _workflow, etc.
```

### Python Native Example
```json
{
  "parameters": {
    "language": "python-native",
    "mode": "runOnceForEachItem",
    "pythonCode": "# Limited to _item helper\ndata = _item['json']\n\nreturn {\n    'json': {\n        'original': data,\n        'processed': True\n    }\n}"
  }
}
```

---

## Common Patterns

### Filter Items
```javascript
// Filter items based on condition
const items = $input.all();
return items.filter(item => item.json.status === 'active');
```

### Group Items
```javascript
// Group items by key
const items = $input.all();
const grouped = {};

for (const item of items) {
  const key = item.json.category;
  if (!grouped[key]) {
    grouped[key] = [];
  }
  grouped[key].push(item.json);
}

return Object.entries(grouped).map(([category, items]) => ({
  json: { category, items, count: items.length }
}));
```

### Aggregate Data
```javascript
// Sum values
const items = $input.all();
const total = items.reduce((sum, item) => sum + item.json.amount, 0);

return [{ json: { total, count: items.length } }];
```

### Parse JSON String
```javascript
// Parse JSON string field
const item = $input.item;
const parsed = JSON.parse(item.json.jsonString);

return {
  json: {
    ...item.json,
    parsed
  }
};
```

### External HTTP Call
```javascript
// Make HTTP request (requires Code node options)
const response = await fetch('https://api.example.com/data', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${$env.API_KEY}`
  },
  body: JSON.stringify($input.item.json)
});

const data = await response.json();
return { json: data };
```

### Handle Binary Data
```javascript
// Access binary data
const items = $input.all();

return items.map(item => ({
  json: {
    fileName: item.binary?.data?.fileName,
    mimeType: item.binary?.data?.mimeType,
    fileSize: item.binary?.data?.fileSize
  },
  binary: item.binary
}));
```

---

## Return Format

### Single Item
```javascript
return {
  json: { key: 'value' }
};
```

### Multiple Items
```javascript
return [
  { json: { id: 1 } },
  { json: { id: 2 } },
  { json: { id: 3 } }
];
```

### With Binary Data
```javascript
return {
  json: { fileName: 'output.txt' },
  binary: {
    data: {
      data: Buffer.from('Hello World').toString('base64'),
      mimeType: 'text/plain',
      fileName: 'output.txt'
    }
  }
};
```

---

## Error Handling

### Throw Error
```javascript
if (!$input.item.json.required_field) {
  throw new Error('Missing required field');
}
```

### Try/Catch
```javascript
try {
  const result = JSON.parse($input.item.json.jsonString);
  return { json: result };
} catch (error) {
  return {
    json: {
      error: error.message,
      original: $input.item.json.jsonString
    }
  };
}
```

---

## Anti-Patterns (AVOID)

### 1. Use Code for Simple Transforms
```javascript
// WRONG - Use Set node instead
return [{
  json: {
    newField: $input.item.json.oldField
  }
}];
```

### 2. Use Code for Simple Conditions
```javascript
// WRONG - Use IF node instead
if ($input.item.json.status === 'active') {
  return [{ json: $input.item.json }];
}
return [];
```

### 3. Forget Return Statement
```javascript
// WRONG - Must return items
const processed = $input.all().map(i => i.json);
// Missing return!

// CORRECT
return $input.all().map(i => ({ json: i.json }));
```

---

## Validation Checklist

- [ ] Using typeVersion 2
- [ ] Language specified (javaScript, python, python-native)
- [ ] Mode specified (runOnceForAllItems or runOnceForEachItem)
- [ ] Code returns proper format (array of objects with json property)
- [ ] Considered if native node would be simpler
- [ ] Error handling for external calls
- [ ] No sensitive data logged
