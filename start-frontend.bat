@echo off
REM CareerPilot AI — start frontend (Next.js on :3001). Run from project root.
cd /d "%~dp0frontend"
npm run dev -- -p 3001
