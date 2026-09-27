#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$DIR/.venv/bin/activate"

# Run Streamlit app
echo "🚀 Starting Interlock System..."
streamlit run "$DIR/app.py"
