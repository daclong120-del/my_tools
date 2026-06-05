@echo off
title SocialPeta Downloader CLI
chcp 65001 > nul
cd /d "%~dp0"
cd ..\..\..

if not "%~1"=="" (
    .venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py %*
) else (
    .venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py
)
