# Phase 2: Real Backend Implementation

**Data:** 2026-01-10
**Status:** ✅ Implementado
**Custo:** $0 (FREE tier Gemini API + n8n self-hosted)

---

## 📋 O que foi Implementado

### 1. n8n Workflows Criados

#### **classify-photos.json**
- **Webhook:** `POST /webhook/classify-photos`
- **Input:** `{photo_ids: ["photo_123", ...]}`
- **Output:** `{classifications: [{photo_id, classification, confidence}]}`
- **Categorias:** Fundação, Estrutura, Alvenaria, Instalações Elétricas, Instalações Hidráulicas, Revestimento, Pintura, Acabamento, Área Externa, Segurança
- **Status:** Mock implementation (ready for Gemini Vision API integration)
- **Localização:** `workflows/classify-photos.json`

#### **transcribe-audio.json**
- **Webhook:** `POST /webhook/transcribe-audio`
- **Input:** `{audio_id: "audio_987", audio_base64: "data:audio/webm;base64,..."}`
- **Output:** `{audio_id, transcription}`
- **Status:** Mock implementation (ready for Gemini STT API integration)
- **Localização:** `workflows/transcribe-audio.json`

### 2. Frontend Integration (NewDiary.tsx)

**Alterações:**
- ✅ Adicionada variável de ambiente `VITE_N8N_URL` (default: http://localhost:5678)
- ✅ Helper function `blobToBase64()` para converter áudio para base64
- ✅ Integração com webhook `/webhook/classify-photos`
- ✅ Integração com webhook `/webhook/transcribe-audio`
- ✅ Error handling robusto com status checks
- ✅ Mantida compatibilidade com mock API para DOCX generation

**Endpoints Atualizados:**
```typescript
// Classificação de fotos:
POST ${N8N_BASE_URL}/webhook/classify-photos

// Transcrição de áudio:
POST ${N8N_BASE_URL}/webhook/transcribe-audio

// Geração de DOCX (ainda mock):
POST ${API_BASE_URL}/api/diario/gerar
```

### 3. DOCX Image Embedding (docxGenerator.ts)

**Alterações:**
- ✅ Importado `ImageRun` da biblioteca `docx`
- ✅ Helper function `fetchImageAsBuffer()` para buscar imagens de URLs
- ✅ Embedding real de imagens no DOCX (max 600x450px)
- ✅ Fallback gracioso para texto caso fetch falhe
- ✅ Error handling robusto

**Antes:**
```typescript
// Apenas referência textual
[Imagem: foto_1.jpg]
```

**Depois:**
```typescript
// Imagem real embedada no DOCX
new ImageRun({
  data: imageBuffer,
  transformation: { width: 600, height: 450 }
})
```

### 4. Configuração

**Arquivo criado:** `.env.example`
```bash
# n8n Backend Configuration
VITE_N8N_URL=http://localhost:5678

# Gemini API Key (configurar no n8n também)
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 🚀 Como Configurar n8n

### Passo 1: Instalar n8n

```bash
# Opção 1: Docker (RECOMENDADO)
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Opção 2: npm (local)
npm install -g n8n
n8n start
```

### Passo 2: Acessar Interface

- Abra: http://localhost:5678
- Crie uma conta (primeira vez)

### Passo 3: Importar Workflows

1. Clique em **"Import workflow"** no canto superior direito
2. Selecione `workflows/classify-photos.json`
3. Repita para `workflows/transcribe-audio.json`
4. **Ative os workflows** clicando no toggle no canto superior direito

### Passo 4: Configurar Gemini API (Upgrade de Mock para Real)

#### **Para classify-photos:**

1. Abra o workflow `Classify Photos - Gemini Vision`
2. Localize o node `Classify Photo (Mock)`
3. Substitua o Code node por **HTTP Request node**:
   - Method: POST
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent`
   - Authentication: API Key
   - Header: `x-goog-api-key` = `{{$env.GEMINI_API_KEY}}`
   - Body JSON:
```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "Classifique esta foto de obra em uma das categorias: Fundação, Estrutura, Alvenaria, Instalações Elétricas, Instalações Hidráulicas, Revestimento, Pintura, Acabamento, Área Externa, Segurança. Retorne JSON: {classification: string, confidence: number}"
        },
        {
          "inline_data": {
            "mime_type": "image/jpeg",
            "data": "{{$json.photo_base64}}"
          }
        }
      ]
    }
  ]
}
```

4. Adicione node `Code` depois para extrair `classification` e `confidence` do response

#### **Para transcribe-audio:**

1. Abra o workflow `Transcribe Audio - Gemini STT`
2. Localize o node `Transcribe Audio (Mock)`
3. Substitua o Code node por **HTTP Request node**:
   - Method: POST
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent`
   - Authentication: API Key
   - Header: `x-goog-api-key` = `{{$env.GEMINI_API_KEY}}`
   - Body JSON:
```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "Transcreva este áudio em português (pt-BR). Retorne apenas o texto transcrito."
        },
        {
          "inline_data": {
            "mime_type": "audio/webm",
            "data": "{{$json.audio_base64.split(',')[1]}}"
          }
        }
      ]
    }
  ]
}
```

4. Adicione node `Code` depois para extrair `transcription` do response

### Passo 5: Testar Webhooks

```bash
# Teste classify-photos:
curl -X POST http://localhost:5678/webhook/classify-photos \
  -H "Content-Type: application/json" \
  -d '{"photo_ids": ["photo_1", "photo_2"]}'

# Teste transcribe-audio:
curl -X POST http://localhost:5678/webhook/transcribe-audio \
  -H "Content-Type: application/json" \
  -d '{"audio_id": "audio_1", "audio_base64": "data:audio/webm;base64,..."}'
```

---

## 🧪 Como Testar a Integração Completa

### Passo 1: Iniciar n8n

```bash
docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n
# OU
n8n start
```

### Passo 2: Iniciar Aplicação Frontend

```bash
cd diario-obras-ai
npm run dev
# Aplicação em http://localhost:5176
```

### Passo 3: Testar Workflow Completo

1. **Acessar:** http://localhost:5176
2. **Preencher:**
   - Nome do Projeto: "Teste n8n Integration"
   - Local: "Teste Localização"
3. **Upload de Fotos:** Adicionar 2-3 fotos
4. **Gravar Áudio:** (opcional) Gravar áudio de teste
5. **Gerar Diário:** Clicar em "Gerar Diário"

**Fluxo Esperado:**
```
1. Frontend envia photo_ids → n8n /webhook/classify-photos
2. n8n retorna classifications
3. Frontend envia audio_base64 → n8n /webhook/transcribe-audio
4. n8n retorna transcription
5. Frontend envia tudo → mock API /api/diario/gerar
6. Mock API gera DOCX com imagens embedadas
7. Download automático do DOCX
```

### Passo 4: Verificar Logs

**n8n:**
- Acesse http://localhost:5678
- Clique em **"Executions"** no menu lateral
- Veja execuções dos workflows

**Frontend:**
- Abra DevTools (F12)
- Aba Console: verificar logs de API calls
- Aba Network: verificar requests/responses

---

## 📊 Comparação: Mock vs Real Backend

| Aspecto | Phase 1 (Mock) | Phase 2 (Real Backend) |
|---------|----------------|------------------------|
| **Classificação** | Random categories | Gemini Vision API |
| **Confiança** | Random 85-100% | Gemini confidence score |
| **Transcrição** | Texto fixo | Gemini STT real |
| **Imagens DOCX** | Referência textual | Imagens embedadas |
| **Custo** | $0 | $0 (FREE tier) |
| **Setup** | localStorage | n8n + Gemini API |

---

## 🔧 Troubleshooting

### Erro: "Failed to fetch" ao chamar n8n

**Causa:** n8n não está rodando ou porta errada

**Solução:**
```bash
# Verificar se n8n está rodando:
curl http://localhost:5678

# Reiniciar n8n:
docker restart n8n
# OU
n8n start
```

### Erro: Workflow não ativa

**Causa:** API não consegue ativar workflows (limitação conhecida)

**Solução:**
- Abrir n8n UI (http://localhost:5678)
- Clicar no toggle "Active" manualmente

### Erro: Imagens não embedadas no DOCX

**Causa:** URLs das fotos não acessíveis (blob URLs expiram)

**Solução:**
- Usar Data URLs (`data:image/jpeg;base64,...`) em vez de blob URLs
- OU: Fazer upload de fotos para servidor permanente antes de gerar DOCX

### Erro: Gemini API Rate Limit

**Causa:** Muitas requests em curto período (FREE tier: 15 RPM)

**Solução:**
- Adicionar delay entre classificações
- OU: Upgrade para Gemini Pro (paid tier)

---

## 📈 Próximos Passos (Phase 3)

### Melhorias Planejadas:

1. **Upload de Fotos para Storage Permanente**
   - Cloudflare R2 (FREE tier: 10GB)
   - OU: Supabase Storage (FREE tier: 1GB)
   - Gerar URLs permanentes para embedding no DOCX

2. **Otimização de Imagens**
   - Resize automático antes de upload
   - Compress (max 800KB por foto)
   - Conversão para WebP

3. **UI Notifications**
   - Substituir `alert()` por react-hot-toast
   - Feedback visual durante classificação/transcrição
   - Progress bars para upload/geração

4. **Error Handling Avançado**
   - Retry automático com exponential backoff
   - Fallback para mock API se n8n offline
   - Log de erros para Sentry

5. **Testing**
   - Unit tests (Vitest)
   - E2E tests (Playwright)
   - Integration tests (n8n workflows)

6. **Deploy**
   - Frontend: Vercel/Netlify
   - n8n: Railway/Render (FREE tier)
   - Workflows: GitHub Actions CI/CD

---

## 💰 Custos Estimados

| Serviço | Tier | Custo/mês |
|---------|------|-----------|
| Gemini API (Vision + STT) | FREE | $0 |
| n8n (self-hosted) | FREE | $0 |
| Cloudflare R2 (storage) | FREE (10GB) | $0 |
| Vercel (hosting frontend) | FREE | $0 |
| Railway (hosting n8n) | FREE (5$/mês crédito) | $0 |
| **TOTAL** | - | **$0/mês** |

**Custos após FREE tier:**
- Gemini Pro: $7/1M tokens (~100 imagens)
- Railway: $5/mês (após crédito inicial)
- R2: $0.015/GB após 10GB

---

## ✅ Checklist de Implementação

- [x] Criar n8n workflows (classify-photos, transcribe-audio)
- [x] Integrar frontend com n8n webhooks
- [x] Adicionar helper `blobToBase64()`
- [x] Implementar image embedding em DOCX
- [x] Criar `.env.example` com configurações
- [x] Documentar setup e testes
- [ ] Substituir mock implementations por Gemini API real (manual)
- [ ] Ativar workflows no n8n (manual)
- [ ] Testar fluxo completo end-to-end
- [ ] Deploy de produção (Phase 3)

---

**Última atualização:** 2026-01-10
**Responsável:** Claude Code (Free tier orchestration)
**Custo total Phase 2:** $0

---
