@echo off
REM Docker Cleanup Script for Jenkins Build Agent
REM This script can be run manually or scheduled to clean up Docker resources

echo =========================================
echo Docker Cleanup Script
echo Started: %date% %time%
echo =========================================

REM Stop all running containers
echo.
echo [1/6] Stopping all running containers...
FOR /f "tokens=*" %%i IN ('docker ps -q 2^>nul') DO (
    echo Stopping container: %%i
    docker stop %%i 2>nul
)

REM Remove all stopped containers
echo.
echo [2/6] Removing stopped containers...
docker container prune -f 2>nul
if %errorlevel% neq 0 echo No containers to remove

REM Remove images from your registry (customize the registry URL)
echo.
echo [3/6] Removing images from Artifactory registry...
FOR /f "tokens=*" %%i IN ('docker images --format "{{.Repository}}:{{.Tag}}" ^| findstr "trialqlk1tc.jfrog.io" 2^>nul') DO (
    echo Removing: %%i
    docker rmi %%i 2>nul || echo Failed to remove %%i
)

REM Remove dangling images
echo.
echo [4/6] Removing dangling images...
docker image prune -f 2>nul
if %errorlevel% neq 0 echo No dangling images

REM Clean build cache older than 24 hours
echo.
echo [5/6] Cleaning Docker build cache (older than 24h)...
docker builder prune -f --filter "until=24h" 2>nul
if %errorlevel% neq 0 echo No build cache to clean

REM Remove unused volumes
echo.
echo [6/6] Removing unused volumes...
docker volume prune -f 2>nul
if %errorlevel% neq 0 echo No unused volumes

REM Show disk usage after cleanup
echo.
echo =========================================
echo Cleanup completed!
echo =========================================
echo.
echo Docker disk usage after cleanup:
docker system df

REM Show remaining images
echo.
echo Remaining Docker images:
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo.
echo =========================================
echo Cleanup finished: %date% %time%
echo =========================================

pause