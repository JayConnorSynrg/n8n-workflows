import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import TestUIStates from './test-ui-states'
import './styles/globals.css'

// Check URL for test mode: ?test=ui
const params = new URLSearchParams(window.location.search)
const isTestMode = params.get('test') === 'ui'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isTestMode ? <TestUIStates /> : <App />}
  </React.StrictMode>,
)

// Expose event bus for Playwright testing (dev only)
if (import.meta.env.DEV) {
  import('./lib/AgentEventBus').then(({ agentEventBus }) => {
    (window as any).__dispatchAgentEvent = (event: unknown) => agentEventBus.dispatchRaw(event)
    ;(window as any).__resetStore = () => {
      import('./lib/store').then(({ useStore }) => useStore.getState().reset())
    }
  })
}
