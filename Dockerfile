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

# Copy project files PRIMA di cambiare utente
COPY pyproject.toml ./
COPY src/ ./src/
COPY .env ./

# Install dependencies globally (no venv) come ROOT
# Usa PyTorch CPU-only per ridurre dimensione immagine e tempo di build
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision --no-cache-dir && \
    uv sync

# Create non-root user and change ownership DOPO l'installazione
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "python", "-m", "src.rag_gestionale.api.main"]