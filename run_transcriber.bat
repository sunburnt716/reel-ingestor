@echo off
REM ---------------------------------------------------------------
REM run_transcriber.bat
REM Wrapper so Windows Task Scheduler runs the script with the
REM correct working directory and the SAME Python that has the
REM packages installed.
REM ---------------------------------------------------------------

REM Folder containing reel_transcriber.py
set PROJECT_DIR=C:\Users\swaya\Projects\reel-ingestor\reel-ingestor

REM The exact Python the packages were installed into (WindowsApps Store Python)
set PYTHON=C:\Users\swaya\AppData\Local\Microsoft\WindowsApps\python3.12.exe

cd /d "%PROJECT_DIR%"
"%PYTHON%" reel_transcriber.py