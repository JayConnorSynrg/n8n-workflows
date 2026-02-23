# AIO Voice System — E2E Tests

## Prerequisites

The dev server must be running before executing tests:

```bash
npm run dev
# or
npm run start
```

## Run tests (headed — watch execution)

```bash
npx playwright test --headed
```

## Run specific test file

```bash
npx playwright test full-session --headed
```

## Run a single test by title

```bash
npx playwright test --headed -g "emailSend — complete tool lifecycle"
```

## Run with custom server URL

```bash
TEST_BASE_URL=http://localhost:3000 npx playwright test
```

## Run in CI (headless, default)

```bash
npm run test:e2e
```

## Interactive UI mode

```bash
npm run test:e2e:ui
```

## View HTML report after run

```bash
npx playwright show-report
```

## Screenshots

Failure screenshots and pass screenshots saved to `e2e/screenshots/`.

## Test inventory (`full-session.spec.ts`)

| # | Test | Script | Expected outcome |
|---|------|--------|-----------------|
| 1 | loads app with replay panel | emailSend | Panel, script selector, play btn visible |
| 2 | emailSend — complete tool lifecycle | emailSend | 1 card reaches `completed` |
| 3 | multiTool — two sequential tools complete in order | multiTool | 2 cards reach `completed` |
| 4 | errorRecovery — tool error state renders correctly | errorRecovery | 1 card reaches `error` |
| 5 | concurrent — three tools fire simultaneously | concurrent | 3 cards all reach `completed` |
| 6 | replay controls — pause and restart work | emailSend | Pause freezes label; restart resets progress |
| 7 | agent state label reflects session state | emailSend | `thinking` → `speaking` transitions |
| 8 | waitForToolCard helper smoke test | emailSend | Helper resolves on `sendEmail` completed |

## data-status values

`pending | executing | completed | error`

Note: `tool_result.status="failed"` maps to store `ToolCall.status="error"`.
