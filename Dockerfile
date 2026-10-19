# --- Build the widget and the admin dashboard
FROM node:22-slim AS web
WORKDIR /build
COPY widget/package*.json widget/
RUN cd widget && npm ci
COPY admin/package*.json admin/
RUN cd admin && npm ci
COPY widget widget
COPY admin admin
RUN cd widget && npm run build && cd ../admin && npm run build

# --- Python app
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/models \
    DATA_DIR=/app/data \
    PORT=7860
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Download the embedding model at build time, so the container starts fast and offline.
ENV EMBED_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(os.environ['EMBED_MODEL'])"

COPY backend backend
COPY demo-site demo-site
COPY --from=web /build/widget/dist widget/dist
COPY --from=web /build/admin/dist admin/dist

# Run as a non-root user (Hugging Face Spaces requires uid 1000).
RUN useradd -m -u 1000 app && mkdir -p /app/data && chown -R app /app
USER app

WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
