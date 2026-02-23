# Update: "Prepare DB Insert" Node - Fixed Code

**Workflow ID:** `IamjzfFxjHviJvJg`
**Node ID:** `merge-extractions`
**Node Name:** "Prepare DB Insert"
**Date:** 2026-01-31

## Issue
The original code used `$input.first()` which only processes the FIRST item from the extraction nodes. This causes data loss when multiple files are being processed simultaneously (e.g., when Route By MIME Type splits files to different extraction paths that converge).

## Solution
Updated to use `$input.getAll().map()` to process ALL items returned from the extraction nodes.

## Updated Code

Replace the jsCode parameter in the "Prepare DB Insert" node with:

```javascript
return $input.getAll().map((item, itemIndex) => {
  const downloadNodeData = item.json || {};

  // Check if this is an error response
  if (downloadNodeData.error || (!downloadNodeData.text && !downloadNodeData.data && !downloadNodeData.id)) {
    const errorMsg = downloadNodeData.error?.message || downloadNodeData.message || 'Extraction failed';
    return {
      json: {
        drive_file_id: 'error',
        drive_folder_id: '11KcezPe3NqgcC3TNvHxAAZS4nPYrMXRF',
        file_name: 'error',
        mime_type: 'error',
        file_size_bytes: 0,
        web_view_link: '',
        extracted_text: errorMsg,
        text_length: 0,
        extraction_method: 'error',
        drive_modified_time: null,
        extraction_status: 'FAILED'
      }
    };
  }

  // Get extracted text from extraction nodes
  const extractedText = downloadNodeData.text || downloadNodeData.data || '';

  // Fallback: construct from available data in the item
  const fileId = downloadNodeData.id || downloadNodeData.drive_file_id || 'unknown';
  const fileName = downloadNodeData.name || downloadNodeData.file_name || 'unknown';
  const mimeType = downloadNodeData.mimeType || downloadNodeData.mime_type || 'application/octet-stream';
  const webViewLink = downloadNodeData.webViewLink || downloadNodeData.web_view_link || '';
  const modifiedTime = downloadNodeData.modifiedTime || downloadNodeData.drive_modified_time || null;

  const rawSize = downloadNodeData.size || downloadNodeData.file_size_bytes;
  const fileSize = (typeof rawSize === 'number') ? rawSize :
                   (typeof rawSize === 'string' && /^\d+$/.test(rawSize)) ? parseInt(rawSize, 10) : 0;

  const textLength = typeof extractedText === 'string' ? extractedText.length : 0;

  return {
    json: {
      drive_file_id: fileId,
      drive_folder_id: '11KcezPe3NqgcC3TNvHxAAZS4nPYrMXRF',
      file_name: fileName,
      mime_type: mimeType,
      file_size_bytes: fileSize,
      web_view_link: webViewLink,
      extracted_text: extractedText,
      text_length: textLength,
      extraction_method: 'auto',
      drive_modified_time: modifiedTime,
      extraction_status: 'SUCCESS'
    }
  };
});
```

## Key Changes

| Aspect | Before | After |
|--------|--------|-------|
| Method | `$input.first()` | `$input.getAll()` |
| Processing | Single item (first only) | All items via `.map()` |
| Return | Single object in array | Array of objects (one per item) |
| Metadata Source | Direct from item | Item data or fallback fields |
| Error Handling | Basic | Per-item error detection |

## Testing

After updating the node:
1. Validate the workflow: `mcp__n8n-mcp__n8n_validate_workflow` with ID `IamjzfFxjHviJvJg`
2. Test with multiple files going through different extraction paths
3. Verify all documents are inserted into the database (not just the first one)

## Implementation Notes

- The code now handles all extraction methods: PDF, DOCX, Text, Image, CSV
- Error responses are wrapped with a 'FAILED' status
- File metadata is extracted from each item's json object
- Size field is safely parsed (number or numeric string)
- Text length is always calculated from extracted content

## Deployment Status

Ready for manual deployment to n8n UI:
1. Open workflow `IamjzfFxjHviJvJg` in n8n
2. Edit the "Prepare DB Insert" node
3. Replace the code parameter with the updated code above
4. Save the workflow

Complete workflow file with this update: `/tmp/full_workflow_updated.json`
