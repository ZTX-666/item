# 🚀 SETUP - Diário de Obras.AI

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Node.js 18+ (para desenvolvimento frontend)
- Conta Google com acesso ao Gemini API

---

## 🔑 1. Configurar Variáveis de Ambiente

### Passo 1: Copiar arquivo de exemplo

```bash
cp .env.example .env
```

### Passo 2: Obter chave do Gemini API

1. Acesse: **https://aistudio.google.com/apikey**
2. Faça login com sua conta Google
3. Clique em **"Create API Key"**
4. Copie a chave gerada

### Passo 3: Editar arquivo .env

Abra o arquivo `.env` e cole sua chave:

```env
GEMINI_API_KEY=sua_chave_aqui
```

**⚠️ IMPORTANTE:**
- NUNCA commite o arquivo `.env` no Git
- O arquivo `.env.example` está no Git como referência
- O arquivo `.env` está no `.gitignore` por segurança

---

## 🐳 2. Iniciar Aplicação com Docker

### Opção A: Docker Compose (RECOMENDADO)

```bash
# Buildar e iniciar todos os serviços
docker-compose up --build -d

# Ver logs
docker-compose logs -f backend

# Parar serviços
docker-compose down
```

### Opção B: Apenas Backend (desenvolvimento)

```bash
# Backend
cd backend
docker build -t diario-obras-backend .
docker run -p 8000:8000 --env-file ../.env diario-obras-backend

# Frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

---

## 🧪 3. Testar Aplicação

### Backend (http://localhost:8000)

```bash
# Health check
curl http://localhost:8000/

# Upload de foto
curl -X POST "http://localhost:8000/api/fotos/upload" \
  -F "file=@caminho/para/foto.jpg"

# Classificar foto (retorna ID ao fazer upload)
curl -X POST "http://localhost:8000/api/fotos/classificar" \
  -H "Content-Type: application/json" \
  -d '["photo_id_aqui"]'
```

### Frontend (http://localhost:5173)

1. Abra http://localhost:5173 no navegador
2. Preencha os dados do projeto
3. Faça upload de fotos e áudios
4. Clique em "Gerar Relatório"

---

## 📊 4. Estrutura de Pastas

```
DIARIO DE OBRAS.AI/
├── .env                    # ⚠️ SEU ARQUIVO COM CHAVES (não versionar!)
├── .env.example            # ✅ Template versionado
├── .gitignore              # ✅ Proteção de arquivos sensíveis
├── docker-compose.yml      # Orquestração Docker
├── backend/
│   ├── main.py            # API FastAPI
│   ├── models.py          # Modelos de dados
│   ├── requirements.txt   # Dependências Python
│   ├── Dockerfile         # Imagem Docker
│   ├── uploads/           # Fotos e áudios (não versionado)
│   └── output/            # DOCx gerados (não versionado)
└── frontend/
    ├── src/               # Código React
    ├── package.json       # Dependências Node
    └── vite.config.ts     # Config Vite
```

---

## 🔧 5. Troubleshooting

### "API key expired"

**Solução:** Gere nova chave em https://aistudio.google.com/apikey

### "Port 8000 already in use"

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <numero_do_pid> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### "Backend em modo MOCK"

Verifique se:
1. Arquivo `.env` existe
2. `GEMINI_API_KEY` está preenchida
3. Docker Compose reiniciado: `docker-compose restart backend`

---

## 🆘 Suporte

- Documentação completa: `RELATORIO-FASE4-COMPLETA-2026-01-09.md`
- Testes: `RELATORIO-TESTES-COMPLETO-2026-01-09.md`

---

## ✅ Checklist de Setup

- [ ] Copiado `.env.example` para `.env`
- [ ] Obtida chave do Gemini API
- [ ] Chave adicionada ao `.env`
- [ ] Docker Compose iniciado: `docker-compose up -d`
- [ ] Backend respondendo em http://localhost:8000
- [ ] Frontend respondendo em http://localhost:5173
- [ ] Testado upload de foto
- [ ] Testado classificação com Gemini Vision
- [ ] Gerado relatório DOCX com sucesso

**Pronto! Aplicação configurada e rodando.** 🎉
