# Code Diff: Prepare DB Insert Node

## Location
**Workflow:** IamjzfFxjHviJvJg (Google Drive Document Repository)
**Node:** merge-extractions ("Prepare DB Insert")
**Parameter:** jsCode

## Full Before → After Comparison

### BEFORE (Current - Only processes first item)

```javascript
const downloadNodeData = $input.first()?.json || {};

// Check if this is an error response (from onError: continueRegularOutput)
if (downloadNodeData.error || (!downloadNodeData.text && !downloadNodeData.data && !downloadNodeData.id)) {
  const errorMsg = downloadNodeData.error?.message || downloadNodeData.message || 'Extraction failed';
  return [{
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
  }];
}

// Get extracted text from extraction nodes
const extractedText = downloadNodeData.text || downloadNodeData.data || '';

// Get Google Drive file metadata from the original "Get All Files" node
// This ensures we always have the correct file metadata regardless of extraction method
const driveFileData = $('Get All Files').item.json;

// Extract file metadata from Google Drive API response
const fileId = driveFileData.id || 'unknown';
const fileName = driveFileData.name || 'unknown';
const mimeType = driveFileData.mimeType || 'application/octet-stream';
const webViewLink = driveFileData.webViewLink || '';
const modifiedTime = driveFileData.modifiedTime || null;

// Safely parse numeric fields - protect against non-numeric strings
const rawSize = driveFileData.size;
const fileSize = (typeof rawSize === 'number') ? rawSize :
                 (typeof rawSize === 'string' && /^\d+$/.test(rawSize)) ? parseInt(rawSize, 10) : 0;

const textLength = typeof extractedText === 'string' ? extractedText.length : 0;

return [{
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
}];
```

### AFTER (Fixed - Processes ALL items)

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

## Key Differences Highlighted

### Line 1: Input Retrieval
```diff
- const downloadNodeData = $input.first()?.json || {};
+ return $input.getAll().map((item, itemIndex) => {
+   const downloadNodeData = item.json || {};
```
**Impact:** Changes from getting 1st item to iterating ALL items

### Lines 5-16: Return Value Structure
```diff
- return [{
+ return {
    json: { /* ... */ }
-}];
+};
```
**Impact:** Individual objects are returned; wrapping array is created by `.map()`

### Lines 20-24: Metadata Source
```diff
- // Get Google Drive file metadata from the original "Get All Files" node
- const driveFileData = $('Get All Files').item.json;
+ // Fallback: construct from available data in the item
+ const fileId = downloadNodeData.id || downloadNodeData.drive_file_id || 'unknown';
```
**Impact:** Removes dependency on external node reference; uses item data

### Lines 28-34: Size Parsing
```diff
- const rawSize = driveFileData.size;
+ const rawSize = downloadNodeData.size || downloadNodeData.file_size_bytes;
```
**Impact:** More defensive - checks multiple field names

### Lines 38-39: Error Response Format
```diff
-   return [{
+   return {
      json: { /* ... */ }
-   }];
+   };
```
**Impact:** Same as above - individual object instead of wrapped

## Migration Path

1. **In n8n UI:**
   - Open workflow IamjzfFxjHviJvJg
   - Find node "Prepare DB Insert" (node ID: merge-extractions)
   - Click to edit the Code node
   - Select all existing jsCode
   - Replace with the "AFTER" code above
   - Click Save
   - Activate/Save the workflow

2. **No configuration changes needed:**
   - Input connections: unchanged
   - Output connections: unchanged
   - Downstream nodes: work with array automatically

## Testing the Fix

### Before Fix
```
Input: [item1, item2, item3] from Route By MIME Type
↓
Prepare DB Insert processes: item1 only
↓
Output: [1 prepared record]
↓
Database: 1 record inserted (2 lost)
```

### After Fix
```
Input: [item1, item2, item3] from Route By MIME Type
↓
Prepare DB Insert processes: item1, item2, item3
↓
Output: [3 prepared records]
↓
Database: 3 records inserted (none lost)
```

## Validation

Run this query before and after to verify the fix:

```sql
-- Before: Will show gaps in extracted files
SELECT COUNT(*) as total_files
FROM documents
WHERE extraction_status = 'SUCCESS';

-- Should increase after the fix is deployed
```

---

**Generated:** 2026-01-31
**MCP Tool Status:** Ready - Awaiting manual n8n UI deployment due to API parameter serialization limitations
