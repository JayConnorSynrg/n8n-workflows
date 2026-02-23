import { test, expect, Page } from '@playwright/test'

// Helper: dispatch an event through the exposed bus
async function dispatch(page: Page, event: unknown) {
  await page.evaluate((evt) => (window as any).__dispatchAgentEvent(evt), event)
  await page.waitForTimeout(150) // allow React state update + render
}

// Helper: reset store state
async function resetStore(page: Page) {
  await page.evaluate(() => (window as any).__resetStore())
  await page.waitForTimeout(100)
}

// Helper: wait for a tool card with given data-tool-id to appear
async function waitForCard(page: Page, toolId: string, timeout = 5000) {
  return page.waitForSelector(`[data-testid="tool-call-card"][data-tool-id="${toolId}"]`, { timeout })
}

test.describe('Tool card display — n8n native tools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/?mock=true')
    await page.waitForFunction(() => typeof (window as any).__dispatchAgentEvent === 'function', { timeout: 10000 })
    await resetStore(page)
  })

  test('sendEmail displays as "Email" with ✉️ icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-email-1',
      name: 'sendEmail',
      arguments: { to: 'test@example.com' },
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-email-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toBe('Email')
    const cardText = await card.textContent()
    expect(cardText).toContain('✉️')
  })

  test('searchDrive displays correctly with folder icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-drive-1',
      name: 'searchDrive',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-drive-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toBe('Search Drive')
    const cardText = await card.textContent()
    expect(cardText).toContain('📁')
  })

  test('queryDatabase displays as "Database" with 🗄️ icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-db-1',
      name: 'queryDatabase',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-db-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toBe('Database')
  })

  test('checkContext displays with 🧠 icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-ctx-1',
      name: 'checkContext',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-ctx-1')
    const cardText = await card.textContent()
    expect(cardText).toContain('🧠')
  })
})

test.describe('Tool card display — Composio SCREAMING_CASE slugs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/?mock=true')
    await page.waitForFunction(() => typeof (window as any).__dispatchAgentEvent === 'function', { timeout: 10000 })
    await resetStore(page)
  })

  test('GMAIL_SEND_EMAIL resolves to "Gmail — Send Email" with 📧', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-gmail-1',
      name: 'GMAIL_SEND_EMAIL',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-gmail-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toContain('Gmail')
    expect(text?.trim()).toContain('Send Email')
    const cardText = await card.textContent()
    expect(cardText).toContain('📧')
    // Verify raw slug NOT visible
    expect(cardText).not.toContain('GMAIL_SEND_EMAIL')
  })

  test('GOOGLEDRIVE_LIST_FILES resolves correctly with folder icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-gdrive-1',
      name: 'GOOGLEDRIVE_LIST_FILES',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-gdrive-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toContain('Google Drive')
    const cardText = await card.textContent()
    expect(cardText).not.toContain('GOOGLEDRIVE_LIST_FILES')
  })

  test('MICROSOFTTEAMS_SEND_MESSAGE resolves with 💬 icon', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-teams-1',
      name: 'MICROSOFTTEAMS_SEND_MESSAGE',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-teams-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    expect(text?.trim()).toContain('Microsoft Teams')
    const cardText = await card.textContent()
    expect(cardText).toContain('💬')
    expect(cardText).not.toContain('MICROSOFTTEAMS_SEND_MESSAGE')
  })

  test('unknown Composio slug auto-derives readable name', async ({ page }) => {
    await dispatch(page, {
      type: 'tool.call',
      call_id: 'tc-unknown-1',
      name: 'HUBSPOT_CREATE_CONTACT',
      arguments: {},
      timestamp: Date.now(),
    })
    const card = await waitForCard(page, 'tc-unknown-1')
    const toolName = await card.$('[data-testid="tool-name"]')
    const text = await toolName?.textContent()
    // Should not show raw slug
    expect(text?.trim()).not.toContain('HUBSPOT_CREATE_CONTACT')
    // Should show resolved name containing "HubSpot"
    expect(text?.trim()).toContain('HubSpot')
  })
})

test.describe('Tool card status transitions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/?mock=true')
    await page.waitForFunction(() => typeof (window as any).__dispatchAgentEvent === 'function', { timeout: 10000 })
    await resetStore(page)
  })

  test('card transitions pending → executing → completed', async ({ page }) => {
    const callId = 'tc-transition-1'

    // Step 1: tool.call → pending
    await dispatch(page, { type: 'tool.call', call_id: callId, name: 'sendEmail', arguments: {}, timestamp: Date.now() })
    let card = await waitForCard(page, callId)
    expect(await card.getAttribute('data-status')).toBe('pending')

    // Step 2: composio.searching
    await dispatch(page, { type: 'composio.searching', call_id: callId, tool_slug: 'GMAIL_SEND_EMAIL', detail: '', timestamp: Date.now() })
    await page.waitForTimeout(150)

    // Step 3: composio.executing
    await dispatch(page, { type: 'composio.executing', call_id: callId, tool_slug: 'GMAIL_SEND_EMAIL', detail: '', timestamp: Date.now() })
    // Both panels render the same card; .first() avoids strict-mode violation
    card = page.locator(`[data-testid="tool-call-card"][data-tool-id="${callId}"]`).first()
    await expect(card).toHaveAttribute('data-status', 'executing', { timeout: 2000 })

    // Step 4: composio.completed
    await dispatch(page, { type: 'composio.completed', call_id: callId, tool_slug: 'GMAIL_SEND_EMAIL', detail: '', duration_ms: 1200, timestamp: Date.now() })
    await expect(card).toHaveAttribute('data-status', 'completed', { timeout: 2000 })
  })

  test('n8n tool_result event marks card completed', async ({ page }) => {
    const callId = 'tc-result-1'
    await dispatch(page, { type: 'tool.call', call_id: callId, name: 'queryDatabase', arguments: {}, timestamp: Date.now() })
    await waitForCard(page, callId)

    await dispatch(page, {
      type: 'tool_result',
      task_id: 'task-1',
      call_id: callId,
      tool_name: 'queryDatabase',
      result: 'Found 5 records',
      error: '',
      duration_ms: 800,
      status: 'completed',
      timestamp: Date.now(),
    })
    // Both panels render the same card; .first() avoids strict-mode violation
    const card = page.locator(`[data-testid="tool-call-card"][data-tool-id="${callId}"]`).first()
    await expect(card).toHaveAttribute('data-status', 'completed', { timeout: 2000 })
  })
})
