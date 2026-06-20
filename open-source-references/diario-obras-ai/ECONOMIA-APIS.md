# Como Economizar com LLMs e APIs - Guia 2026

## Resumo Rápido

```
┌─────────────────────────────────────────────────────────┐
│              CUSTO ZERO (ou quase)                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Gemini 2.0 Flash    → 1500 requests/dia GRÁTIS        │
│  Gemini 1.5 Flash    → 1500 requests/dia GRÁTIS        │
│  Cohere Embeddings   → 100.000 tokens/mês GRÁTIS       │
│  Whisper (local)     → ILIMITADO (roda no seu PC)      │
│  Groq (Llama/Mixtral)→ 14.400 requests/dia GRÁTIS     │
│  DeepSeek V3         → Limites generosos GRÁTIS        │
│  Cloudflare Workers AI→ 10.000 neurons/dia GRÁTIS     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## APIs Grátis Detalhadas

### 1. Google Gemini (MELHOR CUSTO-BENEFÍCIO)

| Modelo | Limite Grátis | Uso |
|--------|---------------|-----|
| Gemini 2.0 Flash | 1500 req/dia | VLM, classificar fotos |
| Gemini 1.5 Flash | 1500 req/dia | Texto rápido |
| Gemini 1.5 Pro | 50 req/dia | Análise complexa |

**Como usar:**
```python
import google.generativeai as genai
genai.configure(api_key="sua_key_gratis")
model = genai.GenerativeModel('gemini-2.0-flash')
response = model.generate_content("Classifique esta foto de obra")
```

### 2. Groq (MAIS RÁPIDO)

| Modelo | Limite Grátis | Tokens/min |
|--------|---------------|------------|
| Llama 3.3 70B | 14.400 req/dia | 6000 |
| Mixtral 8x7B | 14.400 req/dia | 5000 |

**Vantagem:** Inferência MUITO rápida (10x mais que outros)

### 3. Cohere (EMBEDDINGS)

| Recurso | Limite Grátis |
|---------|---------------|
| embed-multilingual-v3 | 100.000 tokens/mês |
| Rerank | 10.000 searches/mês |

**Ideal para:** RAG de projetos em português

### 4. Cloudflare Workers AI

| Modelo | Limite Grátis |
|--------|---------------|
| Llama 3.1 8B | 10.000 neurons/dia |
| Whisper | 10.000 neurons/dia |
| BGE Embeddings | 10.000 neurons/dia |

### 5. DeepSeek

| Modelo | Custo |
|--------|-------|
| DeepSeek V3 | Grátis (limites generosos) |
| DeepSeek Coder | Grátis |

**Qualidade:** Surpreendentemente boa, rival do GPT-4

### 6. Modelos Locais (ILIMITADO)

| Modelo | RAM Necessária | Qualidade |
|--------|----------------|-----------|
| Whisper Large V3 | 4GB VRAM | Excelente STT |
| Llama 3.2 3B | 8GB RAM | Bom para tarefas simples |
| Qwen 2.5 7B | 16GB RAM | Muito bom |
| LLaVA | 8GB VRAM | VLM local |

**Como rodar:**
```bash
# Ollama (mais fácil)
ollama run llama3.2

# Whisper
pip install openai-whisper
whisper audio.mp3 --model large-v3 --language pt
```

## Estratégia de Economia

### Pirâmide de Custos

```
         ┌─────────┐
         │ Claude  │ ← Só quando PRECISA (complexo)
         │  Opus   │
         ├─────────┤
         │ GPT-4o  │ ← Fallback se Gemini falhar
         ├─────────┤
         │ Gemini  │ ← PADRÃO (grátis, bom)
         │  Flash  │
         ├─────────┤
         │ Groq    │ ← Volume alto (rápido, grátis)
         │ Llama   │
         ├─────────┤
         │ Local   │ ← Whisper, tarefas repetitivas
         │ Models  │
         └─────────┘
```

### Regras de Ouro

1. **Gemini primeiro** - 1500 req/dia é MUITO
2. **Whisper local** - Áudio NUNCA paga
3. **Batch sempre** - 10 fotos numa request > 10 requests
4. **Cache agressivo** - Mesma foto? Mesma resposta
5. **Claude só no premium** - Usar tokens do plano Max, não API

### Cálculo para Diário de Obras

```
Por relatório:
- 20 fotos × 1 classificação = 20 requests Gemini
- 1 áudio × Whisper local = 0 custo
- 1 geração texto = 1 request Gemini

Total: 21 requests/relatório

Com 1500 req/dia grátis:
→ 71 relatórios/dia SEM PAGAR NADA

Se precisar mais:
→ Gemini API: $0.075/1M tokens
→ 100 relatórios = ~$0.50
```

## Hack do Claude Max

Se você tem plano Claude Max ($100/mês):

```bash
# Executa via CLI, consome tokens do plano, não API
claude --print "Analise esta foto de obra: [base64]"

# Via SSH do n8n
ssh localhost "cd projeto && claude --print 'gere relatório'"
```

**Economia:** Claude API = $15/1M tokens vs Max = "ilimitado"

## Checklist de Setup

- [ ] Criar conta Google AI Studio (Gemini grátis)
- [ ] Criar conta Groq (backup rápido)
- [ ] Criar conta Cohere (embeddings)
- [ ] Instalar Whisper local
- [ ] Configurar Ollama (modelos locais)
- [ ] Setup n8n (orquestração)

## Links Importantes

- Google AI Studio: https://aistudio.google.com
- Groq Console: https://console.groq.com
- Cohere Dashboard: https://dashboard.cohere.com
- Ollama: https://ollama.ai
- Whisper: https://github.com/openai/whisper