@echo off
echo Starting RAG Gestionale API Server...
echo.
echo Make sure Docker services are running:
echo - Qdrant on port 6333
echo - OpenSearch on port 9200
echo - Redis on port 6379 (optional)
echo.
echo You can start them with: docker-compose up -d
echo.
uvicorn src.rag_gestionale.api.main:app --reload --host 0.0.0.0 --port 8000
pause