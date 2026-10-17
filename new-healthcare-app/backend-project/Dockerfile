FROM python:3.12-slim

# Without this, Python block-buffers stdout by default whenever it's not
# connected to a real terminal — exactly the case inside a container. That
# means any plain print() statement (the scheduler's own startup/run
# messages, for instance) can sit in a buffer indefinitely and never
# actually appear in `docker compose logs`, even though the code is running
# correctly. This makes all Python output flush immediately instead.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for psycopg2 (the plain, not -binary, wheel resolution can need these on
# slim images — installing them up front avoids a confusing failure mid pip install)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

EXPOSE 8000

# Deliberately just runs the server — migrations and seeding are explicit, one-time
# steps you run yourself (see the deployment instructions), not automatic on every
# container start. Auto-migrating on startup is exactly the kind of thing that goes
# wrong silently when a migration file has been hand-edited, which this project's
# migration has been.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
