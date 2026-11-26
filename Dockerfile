FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docpilot ./docpilot
COPY data ./data
RUN useradd -m app && mkdir -p results && chown -R app /app
USER app
ENV PORT=8080 DOCPILOT_TRACE_PATH=/app/results/traces.jsonl
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/health'%os.environ.get('PORT','8080'))"
CMD ["sh", "-c", "uvicorn docpilot.api:create_app --factory --host 0.0.0.0 --port ${PORT}"]
