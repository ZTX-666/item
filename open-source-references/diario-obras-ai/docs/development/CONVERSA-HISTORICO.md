# DIARIO-OBRAS.ai

Plano para SaaS de geração de Diários de Obra com IA.

## Arquivos

| Arquivo | Conteúdo |
|---------|----------|
| `CONVERSA-HISTORICO.md` | Histórico das perguntas da conversa original |
| `PLANO-DEV.md` | Plano técnico para desenvolvimento |
| `ECONOMIA-APIS.md` | Guia de APIs grátis e como economizar |

## Resumo do Produto

**Problema:** Engenheiros perdem 2-3h/dia com burocracia de relatórios

**Solução:**
1. Joga fotos do dia
2. Grava áudio explicando
3. Arrasta para organizar
4. Clica GERAR → Diário pronto

## Stack (Custo Zero)

- **VLM:** Gemini Flash (1500 req/dia grátis)
- **LLM:** Gemini Flash (grátis)
- **STT:** Whisper local (ilimitado)
- **Embeddings:** Cohere (100K/mês grátis)
- **Backend:** Python FastAPI
- **Frontend:** React + Tailwind
- **Deploy:** Docker

## Próximo Passo

```bash
# Ler o plano de dev
cat PLANO-DEV.md

# Entender economia
cat ECONOMIA-APIS.md
```

---
Gerado em: 08/01/2026
Autor: Lucas + Claude Code