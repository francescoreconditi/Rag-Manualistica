@echo off
echo Starting RAG Gestionale API Server (Simple Mode)...
echo.
echo Make sure Docker services are running:
echo - Qdrant on port 6333
echo - OpenSearch on port 9200
echo.
echo You can start them with: docker-compose up -d
echo.
echo Using simplified reload configuration to avoid Windows reload issues...
echo.
uv run uvicorn src.rag_gestionale.api.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000
pause
