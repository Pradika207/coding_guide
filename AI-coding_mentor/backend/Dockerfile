FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Keep a supplied project-relative artifact. If it is absent from a clean
# checkout, create the same deterministic synthetic fallback model at build time.
USER app
RUN if [ ! -s ml/artifacts/skill_model.joblib ]; then \
        python -c "from ml.models.skill_predictor import train_skill_model; train_skill_model(enable_tracking=False)"; \
    fi \
    && test -s ml/artifacts/skill_model.joblib

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); body = response.read(); raise SystemExit(0 if response.status == 200 and b'healthy' in body else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]