@echo off
rem Double-click: runs upgrade-agent.ps1 as administrator.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0upgrade-agent.ps1\"'"
