@echo off
echo ========================================
echo   RAG Gestionale - DEVELOPMENT MODE
echo ========================================
echo.
echo Starting API in development mode...
echo No Docker services required!
echo.
python -m src.rag_gestionale.api.main_dev
pause