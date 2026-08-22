import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/index.css'
import App from './App.jsx'

// Тема применяется до первого рендера, чтобы не было вспышки светлой темы
const savedTheme = localStorage.getItem('llm_council_theme')
if (savedTheme === 'dark' || savedTheme === 'light') {
  document.documentElement.dataset.theme = savedTheme
} else if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
  document.documentElement.dataset.theme = 'dark'
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
