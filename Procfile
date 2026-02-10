release: python -m app.db.release_init
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
