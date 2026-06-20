# Dockerfile para Backend - Diário de Obras.AI
# Python 3.11 (compatível com google-generativeai)

FROM python:3.11-slim

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Expor porta
EXPOSE 8000

# Comando de início
CMD ["python", "main.py"]
