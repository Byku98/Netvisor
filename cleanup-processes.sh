#!/usr/bin/env bash
# cleanup-processes.sh — Kill all zombie node and uvicorn processes
# Run this from the NetVisor root to clean up before starting fresh

echo "Cleaning up zombie node processes..."
powershell -c "Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null

echo "Cleaning up zombie python (uvicorn) processes..."
powershell -c "Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null

echo "Waiting for processes to terminate..."
sleep 2

echo "Verifying cleanup..."
NODE_COUNT=$(powershell -c "(Get-Process -Name node -ErrorAction SilentlyContinue | Measure-Object).Count" 2>/dev/null)
PYTHON_COUNT=$(powershell -c "(Get-Process -Name python -ErrorAction SilentlyContinue | Measure-Object).Count" 2>/dev/null)

echo "Node processes remaining: ${NODE_COUNT:-0}"
echo "Python processes remaining: ${PYTHON_COUNT:-0}"

if [ "${NODE_COUNT:-0}" -eq 0 ] && [ "${PYTHON_COUNT:-0}" -eq 0 ]; then
    echo "All clean! Ready to start fresh."
else
    echo "Some processes may still be running. Check manually with:"
    echo "  powershell -c 'Get-Process -Name node,python'"
fi