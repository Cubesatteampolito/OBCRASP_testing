#!/bin/bash
# setup and run
#
# envi directory
VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# activate virtual envi
echo "activating virtual environment"
source "$VENV_DIR/bin/activate"

# install requirements
if [ -f "requirements.txt" ]; then
    echo "installing requirements"
    pip install -r requirements.txt
fi

# exe
python SX1276_TX.py
