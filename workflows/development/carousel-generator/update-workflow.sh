#!/bin/bash
API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjZDZmM2VmYi0xZDE3LTRiMjgtYjJkYy1iYjM4ZjgzMGJlMzAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY1NDExODE2LCJleHAiOjE3Njc5MzQ4MDB9.uPUeRNLgW-fyAy8HCxGzyIrqA6Gszcf7qtyPRccRpDU"
WORKFLOW_FILE="/Users/jelalconnor/CODING/N8N/Workflows/workflows/development/carousel-generator/workflow-FIXED-CLEAN.json"

curl -s -X PUT "https://jayconnorexe.app.n8n.cloud/api/v1/workflows/8bhcEHkbbvnhdHBh" \
  -H "X-N8N-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$WORKFLOW_FILE"
