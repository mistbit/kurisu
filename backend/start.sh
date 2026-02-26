#!/bin/bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if venv exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found! Please create it first."
    exit 1
fi

# Start the application
echo "Starting backend server..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
