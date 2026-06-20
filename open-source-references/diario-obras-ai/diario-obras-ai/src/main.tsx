import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { setupMockApiInterceptor } from './services/mockApi'
import { storageService } from './services/storageService'
import { mockReports } from './data/mockReports'

// Ativar Mock API Interceptor (simula backend)
setupMockApiInterceptor()

// Inicializar localStorage com dados de exemplo (apenas na primeira vez)
if (storageService.getAllReports().length === 0) {
  mockReports.forEach(report => storageService.saveReport(report))
  console.log('✅ Dados de exemplo carregados no localStorage')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
