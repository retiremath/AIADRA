import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { registerStepSmoke } from './smoke'

// Built-Electron STEP smoke hook — only under ?smoke=1 (set by main in smoke mode).
if (new URLSearchParams(window.location.search).has('smoke')) registerStepSmoke()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
