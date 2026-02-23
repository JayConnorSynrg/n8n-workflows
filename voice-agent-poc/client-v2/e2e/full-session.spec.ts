import { test, expect, Page } from 'playwright/test'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wait for a tool card with a specific tool ID and status to become visible.
 * `data-status` reflects Zustand store values: pending | executing | completed | error
 */
async function waitForToolCard(
  page: Page,
  toolId: string,
  status: string,
  timeout = 8000
): Promise<void> {
  await expect(
    page.locator(
      `[data-testid="tool-call-card"][data-tool-id="${toolId}"][data-status="${status}"]`
    )
  ).toBeVisible({ timeout })
}

/** Click the play button in the replay panel. */
async function clickPlay(page: Page): Promise<void> {
  await page.click('[data-testid="replay-play-btn"]')
}

/** Assert step label contains `text` within `timeout` ms. */
async function waitForStepLabel(
  page: Page,
  text: string,
  timeout = 5000
): Promise<void> {
  await expect(page.locator('[data-testid="replay-step-label"]')).toContainText(
    text,
    { timeout }
  )
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe('AIO Full Session E2E', () => {
  // Clear localStorage before each test to avoid stale store state.
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
  })

  // -------------------------------------------------------------------------
  // Test 1 — Panel loads
  // -------------------------------------------------------------------------
  test('loads app with replay panel', async ({ page }) => {
    await page.goto('/?replay=emailSend')

    await expect(page.locator('[data-testid="app-root"]')).toBeVisible()
    await expect(page.locator('[data-testid="session-replay-panel"]')).toBeVisible()

    // The script selector should reflect the active script name.
    const scriptSelect = page.locator('[data-testid="replay-script-select"]')
    await expect(scriptSelect).toBeVisible()
    const selectedValue = await scriptSelect.inputValue()
    expect(selectedValue.toLowerCase()).toContain('email')

    await expect(page.locator('[data-testid="replay-play-btn"]')).toBeVisible()

    await page.screenshot({ path: 'e2e/screenshots/replay-panel-loaded.png' })
  })

  // -------------------------------------------------------------------------
  // Test 2 — emailSend: complete tool lifecycle
  // -------------------------------------------------------------------------
  test('emailSend — complete tool lifecycle', async ({ page }) => {
    await page.goto('/?replay=emailSend')
    await clickPlay(page)

    // Step label must become visible and carry text (proves script dispatched events).
    const stepLabel = page.locator('[data-testid="replay-step-label"]')
    await expect(stepLabel).toBeVisible({ timeout: 3000 })

    // First tool card appears in pending/executing state.
    await expect(
      page.locator('[data-testid="tool-call-card"]').first()
    ).toBeVisible({ timeout: 4000 })

    // Card transitions to completed within 6 s.
    await expect(
      page.locator('[data-testid="tool-call-card"][data-status="completed"]').first()
    ).toBeVisible({ timeout: 6000 })

    // Tool name element is visible inside the card.
    await expect(
      page.locator('[data-testid="tool-name"]').first()
    ).toBeVisible()

    await page.screenshot({ path: 'e2e/screenshots/emailsend-completed.png' })
  })

  // -------------------------------------------------------------------------
  // Test 3 — multiTool: two sequential tools complete in order
  // -------------------------------------------------------------------------
  test('multiTool — two sequential tools complete in order', async ({ page }) => {
    await page.goto('/?replay=multiTool')
    await clickPlay(page)

    // First card appears.
    await expect(
      page.locator('[data-testid="tool-call-card"]').first()
    ).toBeVisible({ timeout: 4000 })

    // Second card appears (total count >= 2).
    await expect(
      page.locator('[data-testid="tool-call-card"]')
    ).toHaveCount(2, { timeout: 6000 })

    // Both cards reach completed within 10 s.
    await expect(
      page.locator('[data-testid="tool-call-card"][data-status="completed"]')
    ).toHaveCount(2, { timeout: 10000 })

    await page.screenshot({ path: 'e2e/screenshots/multitool-both-completed.png' })
  })

  // -------------------------------------------------------------------------
  // Test 4 — errorRecovery: tool error state renders correctly
  // -------------------------------------------------------------------------
  test('errorRecovery — tool error state renders correctly', async ({ page }) => {
    await page.goto('/?replay=errorRecovery')
    await clickPlay(page)

    // A card appears first.
    await expect(
      page.locator('[data-testid="tool-call-card"]').first()
    ).toBeVisible({ timeout: 3000 })

    // Card transitions to error status.
    // Note: schema mapping — tool_result.status="failed" → store ToolCall.status="error"
    await expect(
      page.locator('[data-testid="tool-call-card"][data-status="error"]')
    ).toBeVisible({ timeout: 5000 })

    await page.screenshot({ path: 'e2e/screenshots/error-recovery-card.png' })
  })

  // -------------------------------------------------------------------------
  // Test 5 — concurrent: three tools fire simultaneously
  // -------------------------------------------------------------------------
  test('concurrent — three tools fire simultaneously', async ({ page }) => {
    await page.goto('/?replay=concurrent')
    await clickPlay(page)

    // All three cards appear (allows for any statuses initially).
    await expect(
      page.locator('[data-testid="tool-call-card"]')
    ).toHaveCount(3, { timeout: 5000 })

    // All three reach completed within 10 s.
    await expect(
      page.locator('[data-testid="tool-call-card"][data-status="completed"]')
    ).toHaveCount(3, { timeout: 10000 })

    await page.screenshot({ path: 'e2e/screenshots/concurrent-all-completed.png' })
  })

  // -------------------------------------------------------------------------
  // Test 6 — Replay controls: pause and restart
  // -------------------------------------------------------------------------
  test('replay controls — pause and restart work', async ({ page }) => {
    await page.goto('/?replay=emailSend')
    await clickPlay(page)

    // Allow session to start and dispatch at least one event.
    await page.waitForTimeout(1500)

    // Pause the session.
    await page.click('[data-testid="replay-pause-btn"]')

    const stepLabel = page.locator('[data-testid="replay-step-label"]')
    const labelTextBeforePause = await stepLabel.textContent()

    // Wait briefly — if paused, label must not advance.
    await page.waitForTimeout(500)
    const labelTextAfterPause = await stepLabel.textContent()

    expect(labelTextAfterPause).toBe(labelTextBeforePause)

    // Restart the session — progress should reset.
    await page.click('[data-testid="replay-restart-btn"]')

    // After restart, the progress bar should reflect reset (data-progress near 0).
    const progressBar = page.locator('[data-testid="replay-progress"]')
    await expect(progressBar).toBeVisible({ timeout: 2000 })
    const progressValue = await progressBar.getAttribute('data-progress')
    const progress = parseFloat(progressValue ?? '1')
    expect(progress).toBeLessThanOrEqual(0.1)
  })

  // -------------------------------------------------------------------------
  // Test 7 — Agent state label reflects session state transitions
  // -------------------------------------------------------------------------
  test('agent state label reflects session state', async ({ page }) => {
    await page.goto('/?replay=emailSend')
    await clickPlay(page)

    const stateLabel = page.locator('[data-testid="agent-state-label"]')

    // The agent should enter "thinking" state when a tool call is dispatched.
    await expect(stateLabel).toHaveAttribute('data-state', 'thinking', {
      timeout: 2000,
    })

    // After the tool result arrives the agent transitions to "speaking".
    await expect(stateLabel).toHaveAttribute('data-state', 'speaking', {
      timeout: 4000,
    })
  })

  // -------------------------------------------------------------------------
  // Helper smoke test — waitForToolCard utility (internal validation)
  // -------------------------------------------------------------------------
  test('waitForToolCard helper resolves for completed emailSend card', async ({
    page,
  }) => {
    await page.goto('/?replay=emailSend')
    await clickPlay(page)

    // emailSend script dispatches a single "sendEmail" tool call.
    // We validate the helper against the known tool ID from the script.
    await waitForToolCard(page, 'sendEmail', 'completed', 8000)

    // Also validate the step label helper.
    // The emailSend script should surface a step description; we check for a
    // non-empty string rather than a hardcoded label to stay resilient.
    const labelText = await page
      .locator('[data-testid="replay-step-label"]')
      .textContent()
    expect((labelText ?? '').trim().length).toBeGreaterThan(0)

    // waitForStepLabel helper: verify it resolves for a partial text match.
    // Use a substring likely present in any "email" step description.
    await waitForStepLabel(page, 'email', 5000)
  })
})
