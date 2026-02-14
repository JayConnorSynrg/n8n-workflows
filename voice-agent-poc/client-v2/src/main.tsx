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
