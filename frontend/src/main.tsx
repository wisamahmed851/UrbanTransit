import '@fontsource/overpass/400.css'
import '@fontsource/overpass/500.css'
import '@fontsource/overpass/600.css'
import '@fontsource/overpass/700.css'
import '@fontsource/overpass/800.css'
import './styles/app.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'

// Apply the saved theme (dark by default) before React renders, so no page flashes light.
try {
  const saved = localStorage.getItem('utiq.theme') ?? 'dark'
  if (saved !== 'system') document.documentElement.setAttribute('data-theme', saved)
} catch {
  document.documentElement.setAttribute('data-theme', 'dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
