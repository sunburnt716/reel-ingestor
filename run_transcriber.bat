@echo off
REM ---------------------------------------------------------------
REM run_transcriber.bat
REM Wrapper so Windows Task Scheduler runs the script with the
REM correct working directory and Python environment.
REM
REM EDIT the two paths below to match your machine, then point
REM Task Scheduler at THIS .bat file.
REM ---------------------------------------------------------------

REM Full path to the folder containing reel_transcriber.py
set PROJECT_DIR=C:\Users\swaya\Projects\reel-ingestor

REM Full path to python.exe (run `where python` to find yours)
set PYTHON=python

cd /d "%PROJECT_DIR%"
"%PYTHON%" reel_transcriber.py