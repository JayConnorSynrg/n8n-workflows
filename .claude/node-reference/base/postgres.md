# Postgres Node Reference

> **Node Type**: `n8n-nodes-base.postgres`
> **Latest TypeVersion**: 2.6
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

The Postgres node provides full database integration with PostgreSQL. Supports queries, inserts, updates, upserts, and deletes with batch processing and transaction support.

---

## Operations

| Operation | Description |
|-----------|-------------|
| `executeQuery` | Execute a custom SQL query |
| `insert` | Insert rows into a table |
| `select` | Select rows from a table |
| `update` | Update rows in a table |
| `upsert` | Insert or update rows (requires unique column) |
| `deleteTable` | Delete rows from a table |

---

## Authentication

| Credential Type | Description |
|-----------------|-------------|
| `postgres` | Standard PostgreSQL credentials |

---

## Execute Query

### Basic Query
```json
{
  "name": "Postgres Query",
  "type": "n8n-nodes-base.postgres",
  "typeVersion": 2.6,
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT * FROM users WHERE active = true LIMIT 100"
  },
  "credentials": {
    "postgres": {
      "id": "your-credential-id",
      "name": "Postgres"
    }
  }
}
```

### Parameterized Query
```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT * FROM orders WHERE customer_id = $1 AND status = $2",
    "options": {
      "queryParams": "={{ [$json.customerId, $json.status] }}"
    }
  }
}
```

### Dynamic Query with Expression
```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "={{ $json.sqlQuery }}"
  }
}
```

---

## Insert Operations

### Auto-Map Input Data
```json
{
  "parameters": {
    "operation": "insert",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "users",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "autoMapInputData",
      "value": ""
    }
  }
}
```

### Define Columns Manually
```json
{
  "parameters": {
    "operation": "insert",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "orders",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "defineBelow",
      "value": {
        "mappings": [
          {
            "column": "customer_id",
            "value": "={{ $json.customerId }}"
          },
          {
            "column": "product_name",
            "value": "={{ $json.productName }}"
          },
          {
            "column": "quantity",
            "value": "={{ $json.quantity }}"
          },
          {
            "column": "created_at",
            "value": "={{ $now.toISO() }}"
          }
        ]
      }
    }
  }
}
```

---

## Select Operations

### Basic Select
```json
{
  "parameters": {
    "operation": "select",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "products",
      "mode": "list"
    },
    "returnAll": false,
    "limit": 50,
    "options": {}
  }
}
```

### Select with Where Clause
```json
{
  "parameters": {
    "operation": "select",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "orders",
      "mode": "list"
    },
    "returnAll": true,
    "options": {
      "where": {
        "values": [
          {
            "column": "status",
            "condition": "equal",
            "value": "pending"
          },
          {
            "column": "created_at",
            "condition": "largerOrEqual",
            "value": "={{ $today.minus({ days: 7 }).toISO() }}"
          }
        ]
      },
      "sort": {
        "values": [
          {
            "column": "created_at",
            "direction": "DESC"
          }
        ]
      }
    }
  }
}
```

---

## Update Operations

### Update with Where Clause
```json
{
  "parameters": {
    "operation": "update",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "users",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "defineBelow",
      "value": {
        "mappings": [
          {
            "column": "status",
            "value": "active"
          },
          {
            "column": "updated_at",
            "value": "={{ $now.toISO() }}"
          }
        ]
      }
    },
    "where": {
      "values": [
        {
          "column": "id",
          "value": "={{ $json.userId }}"
        }
      ]
    }
  }
}
```

---

## Upsert Operations

### Upsert (Insert or Update)
```json
{
  "parameters": {
    "operation": "upsert",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "inventory",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "autoMapInputData",
      "value": ""
    },
    "conflictColumns": ["product_id"],
    "options": {
      "updateOnConflict": "update"
    }
  }
}
```

---

## Delete Operations

### Delete Rows
```json
{
  "parameters": {
    "operation": "deleteTable",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "logs",
      "mode": "list"
    },
    "where": {
      "values": [
        {
          "column": "created_at",
          "condition": "smaller",
          "value": "={{ $today.minus({ days: 30 }).toISO() }}"
        }
      ]
    }
  }
}
```

---

## Query Batching Options

| Mode | Description |
|------|-------------|
| `single` | Execute all items in one query (default for SELECT) |
| `independently` | Execute each item separately |
| `transaction` | Execute all in a transaction (rollback on error) |

### Transaction Example
```json
{
  "parameters": {
    "operation": "insert",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "transactions",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "autoMapInputData",
      "value": ""
    },
    "options": {
      "queryBatching": "transaction"
    }
  }
}
```

---

## Where Conditions

| Condition | SQL Equivalent |
|-----------|---------------|
| `equal` | `=` |
| `notEqual` | `!=` |
| `larger` | `>` |
| `largerOrEqual` | `>=` |
| `smaller` | `<` |
| `smallerOrEqual` | `<=` |
| `like` | `LIKE` |
| `in` | `IN` |

---

## Advanced Options

### Output Large Results
```json
{
  "parameters": {
    "operation": "select",
    "options": {
      "outputLargeResults": true,
      "largeResultsOptions": {
        "values": {
          "lowerBound": 0,
          "upperBound": 10000,
          "batchSize": 1000
        }
      }
    }
  }
}
```

### Custom Column Casting
```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT * FROM data",
    "options": {
      "replaceEmptyStrings": true,
      "nodeVersion": 2.6
    }
  }
}
```

---

## ResourceLocator Format

Schema and table use ResourceLocator:

```json
{
  "schema": {
    "__rl": true,
    "value": "public",
    "mode": "list",
    "cachedResultName": "public"
  },
  "table": {
    "__rl": true,
    "value": "users",
    "mode": "list",
    "cachedResultName": "users"
  }
}
```

### By Name
```json
{
  "schema": {
    "__rl": true,
    "value": "my_schema",
    "mode": "id"
  }
}
```

---

## Common Patterns

### Batch Insert from Array
```json
{
  "parameters": {
    "operation": "insert",
    "schema": {
      "__rl": true,
      "value": "public",
      "mode": "list"
    },
    "table": {
      "__rl": true,
      "value": "events",
      "mode": "list"
    },
    "columns": {
      "mappingMode": "autoMapInputData",
      "value": ""
    },
    "options": {
      "queryBatching": "transaction"
    }
  }
}
```

### Lookup with Join
```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = $1",
    "options": {
      "queryParams": "={{ [$json.status] }}"
    }
  }
}
```

---

## TypeVersion 2.6 Features

- Resource mapper for column mapping
- Improved large result handling
- Better NULL/empty string handling
- Transaction support
- Query parameter binding

---

## Validation Checklist

- [ ] Using typeVersion 2.6
- [ ] Credentials configured
- [ ] Operation specified
- [ ] Schema/Table use ResourceLocator format
- [ ] Column mapping configured (autoMap or defineBelow)
- [ ] Where clauses use proper condition operators
- [ ] Parameterized queries used for dynamic values (SQL injection prevention)
- [ ] Query batching mode appropriate for use case
