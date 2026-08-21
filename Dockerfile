FROM python:3.14-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH="/app:/app/apps"

# Install system dependencies
# WeasyPrint (geração de PDF) requer Pango/Cairo no nível de SO, além de
# libffi-dev para o binding cffi e fonts-dejavu (fonte usada nos templates PDF).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    curl \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    fonts-dejavu \
    fonts-urw-base35 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Create a non-root user (matching host UID 1000 for development convenience)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /sbin/nologin appuser

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install project dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY . .

# Create directory for static files and media and set permissions
RUN mkdir -p staticfiles media && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
