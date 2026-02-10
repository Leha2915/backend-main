FROM python:3.11

# Arbeitsverzeichnis im Container
WORKDIR /code

# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*


# Abhängigkeiten installieren
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# App-Verzeichnis kopieren (inkl. main.py!)
COPY ./app /code/app

# FastAPI app startup for both local and Heroku runtime
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]