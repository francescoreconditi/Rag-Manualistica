@echo off
echo ========================================
echo   Starting RAG Gestionale Services
echo ========================================
echo.

echo [1/3] Starting Docker services...
docker-compose up -d

echo.
echo [2/3] Waiting for services to be ready...
echo Checking Qdrant (port 6333)...
:check_qdrant
timeout /t 2 >nul
netstat -an | findstr :6333 | findstr LISTENING >nul
if errorlevel 1 (
    echo Waiting for Qdrant...
    goto check_qdrant
)
echo ✓ Qdrant is ready!

echo Checking OpenSearch (port 9200)...
:check_opensearch
timeout /t 2 >nul
netstat -an | findstr :9200 | findstr LISTENING >nul
if errorlevel 1 (
    echo Waiting for OpenSearch...
    goto check_opensearch
)
echo ✓ OpenSearch is ready!

echo Checking Redis (port 6379)...
:check_redis
timeout /t 2 >nul
netstat -an | findstr :6379 | findstr LISTENING >nul
if errorlevel 1 (
    echo Waiting for Redis...
    goto check_redis
)
echo ✓ Redis is ready!

echo.
echo ========================================
echo   All services are ready!
echo ========================================
echo.
echo [3/3] Starting API server...
echo.

call run_api.bat