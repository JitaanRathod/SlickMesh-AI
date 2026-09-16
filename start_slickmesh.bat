@echo off
title SlickMesh AI - Master Gateway & Live Pipeline
cd /d "%~dp0"
echo =========================================================================
echo   SLICKMESH-AI : Autonomous Maritime Surveillance & Attribution Server
echo   Running Live Satellite Ingestion, U-Net Segmentation & Attribution Engine
echo   Dashboard URL: http://127.0.0.1:8000
echo =========================================================================
python server.py
pause
