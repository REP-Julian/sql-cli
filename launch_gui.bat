@echo off
rem Launch SQLCLI Native Desktop Studio without terminal window
start "" "%~dp0.venv\Scripts\pythonw.exe" -m sqlcli.cli %*
