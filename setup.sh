#!/bin/bash
# =============================================================================
# Deep Research App - Setup Script
# =============================================================================
# This script sets up the development environment using Astral UV.

set -e

echo "=============================================="
echo "Deep Research App - Environment Setup"
echo "=============================================="

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo ""
    echo "UV is not installed. Installing UV..."
    echo ""
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add UV to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    echo ""
    echo "UV installed successfully!"
    echo ""
fi

# Verify UV installation
echo "UV version: $(uv --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment with Python 3.12..."
uv venv --python 3.12

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
uv sync

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "To activate the environment, run:"
echo "  source .venv/bin/activate  # Unix/macOS"
echo "  .venv\\Scripts\\activate    # Windows"
echo ""
echo "To start the app, run:"
echo "  uv run streamlit run app/streamlit_app.py"
echo ""
