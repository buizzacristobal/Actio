FROM python:3.12-slim
# LibreOffice is only needed for /generate-lawsuit?format=pdf. Build with
#   --build-arg WITH_PDF=1   to include it (adds ~500 MB).
ARG WITH_PDF=0
RUN if [ "$WITH_PDF" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation && rm -rf /var/lib/apt/lists/*; fi
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
RUN useradd -r -u 10001 app && chown -R app /srv
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
