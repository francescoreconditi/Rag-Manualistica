@echo off
echo Starting RAG Gestionale Streamlit App...
echo.
echo Make sure the API server is running on http://localhost:8000
echo You can start it with: python -m src.rag_gestionale.api.main
echo.
streamlit run streamlit_app.py --server.port 8501 --server.address localhost
pause