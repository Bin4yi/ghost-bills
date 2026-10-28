import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled locally so the demo works with Wi-Fi off.
import '@fontsource/im-fell-english/400.css'
import '@fontsource/im-fell-english/400-italic.css'
import '@fontsource/eb-garamond/400.css'
import '@fontsource/eb-garamond/400-italic.css'
import '@fontsource/eb-garamond/600.css'
import '@fontsource/courier-prime/400.css'
import '@fontsource/courier-prime/700.css'
import './styles/tokens.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
