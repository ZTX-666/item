# Plano de Desenvolvimento - Diário de Obras SaaS

## Visão Geral

```
USUÁRIO (Engenheiro)
       │
       ▼
┌──────────────────┐
│  Upload Fotos    │ ← Qualquer fonte (celular, drone, pasta)
│  + Áudio         │ ← Instrução do que foi feito
│  + Projetos?     │ ← Opcional, para contexto RAG
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│           PROCESSAMENTO                   │
│  1. VLM classifica fotos (Gemini grátis) │
│  2. STT transcreve áudio (Whisper local) │
│  3. RAG busca contexto (se tiver projeto)│
│  4. LLM gera relatório (Gemini/Claude)   │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│  Interface       │
│  Drag & Drop     │ ← Engenheiro organiza
│  Preview         │ ← Vê antes de gerar
│  Botão GERAR     │
└────────┬─────────┘
         │
         ▼
   DIÁRIO DE OBRA
   (DOCX/PDF)
```

## Stack Tecnológica

| Camada | Tecnologia | Custo |
|--------|------------|-------|
| Frontend | React + Tailwind | Grátis |
| Backend | Python FastAPI | Grátis |
| Orquestração | n8n (self-hosted) | Grátis |
| VLM (fotos) | Gemini 2.0 Flash | Grátis (1500/dia) |
| LLM (texto) | Gemini Flash | Grátis |
| STT (áudio) | Whisper local | Grátis |
| Embeddings | Cohere | Grátis (100K/mês) |
| Vector DB | Qdrant | Grátis (self-host) |
| Database | PostgreSQL | Grátis |
| Deploy | Docker Compose | Grátis |

## Fases de Desenvolvimento

### Fase 1: MVP (1-2 semanas)
- [ ] Frontend: Upload fotos + drag&drop (SortableJS)
- [ ] Backend: Receber fotos, salvar
- [ ] Integrar Gemini Flash para classificar fotos
- [ ] Template básico de Diário de Obra
- [ ] Gerar DOCX simples

### Fase 2: Áudio (1 semana)
- [ ] Gravar/upload áudio no frontend
- [ ] Whisper local para transcrição
- [ ] Incluir transcrição no relatório

### Fase 3: RAG Projetos (2 semanas)
- [ ] Upload de PDFs/projetos
- [ ] Chunking + Embeddings (Cohere)
- [ ] Qdrant para busca vetorial
- [ ] Contexto de projeto no relatório

### Fase 4: Polish (1 semana)
- [ ] Dashboard com histórico
- [ ] Templates customizáveis
- [ ] Export PDF bonito

## Comandos para Começar

```bash
# Criar estrutura
mkdir -p diario-obras/{frontend,backend,docker}
cd diario-obras

# Backend Python
cd backend
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install fastapi uvicorn python-multipart google-generativeai

# Frontend
cd ../frontend
npx create-react-app . --template typescript
npm install @dnd-kit/core @dnd-kit/sortable tailwindcss

# Docker
cd ../docker
# docker-compose.yml com postgres, qdrant, n8n
```

## Git Workflow (Senior Dev)

```bash
# Sempre trabalhar em branches
git checkout -b feature/upload-fotos
# ... desenvolver ...
git add .
git commit -m "feat: implementa upload de fotos com preview"
git push origin feature/upload-fotos

# Merge via PR ou:
git checkout main
git merge feature/upload-fotos
```

## Endpoints Principais

```
POST /api/projeto/upload     → Upload de projeto (PDF)
POST /api/fotos/upload       → Upload batch de fotos
POST /api/audio/upload       → Upload de áudio
GET  /api/fotos/{projeto_id} → Lista fotos do projeto
POST /api/fotos/ordenar      → Salva ordem das fotos
POST /api/diario/gerar       → Gera o relatório
GET  /api/diario/{id}/download → Baixa DOCX/PDF
```