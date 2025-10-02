FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Set working directory
WORKDIR /app

# Create non-root user and change ownership
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY .env ./

# Install dependencies globally (no venv)
RUN uv sync

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "python", "-m", "src.rag_gestionale.api.main"]