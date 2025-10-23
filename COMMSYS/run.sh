#!/bin/bash

# --- Setup and Execution Script for SX1276 Transmitter ---

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_SCRIPT="SX1276_TX.py"
REQUIREMENTS_FILE="requirements.txt"
VENV_NAME="comms_env"

echo "--- Starting SX1276 Transmitter Setup ---"

# 1. Check for Python venv module
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install it first."
    exit 1
fi
if ! python3 -m venv --help &> /dev/null; then
    echo "Warning: python3-venv module is missing. Installing it now..."
    sudo apt update
    sudo apt install -y python3-venv
fi

# 2. Create the virtual environment if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment '$VENV_NAME'..."
    python3 -m venv "$VENV_NAME"
fi

# 3. Activate the virtual environment
echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate"

# 4. Install dependencies
echo "Installing dependencies from $REQUIREMENTS_FILE..."
# NOTE: The RPi.GPIO and spidev modules often require elevated privileges 
# to install system-wide, even though we are installing them in a venv.
# We will run this install command, and if it fails, instruct the user to use sudo.

if pip install -r "$REQUIREMENTS_FILE"; then
    echo "Dependencies installed successfully."
else
    echo "Warning: Dependency installation failed (usually due to missing system headers or permissions)."
    echo "Attempting to install again using sudo. Enter password if prompted."
    # Try with sudo, as RPi.GPIO and spidev often require it
    sudo "$VENV_NAME/bin/pip" install -r "$REQUIREMENTS_FILE"
    if [ $? -ne 0 ]; then
        echo "Fatal Error: Dependency installation failed even with sudo."
        echo "Please ensure 'python3-dev' and 'python3-pip' are installed and try again."
        deactivate
        exit 1
    fi
    echo "Dependencies installed successfully using sudo."
fi

# 5. Execute the Python script
echo ""
echo "--- Executing $PYTHON_SCRIPT ---"
# The script itself might need sudo to access GPIO/SPI hardware, 
# so we recommend the user run the whole shell script with sudo if they encounter errors.

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Note: The Python script needs direct hardware access (GPIO/SPI)."
    echo "If the script fails with 'Permission denied' or 'FileNotFoundError',"
    echo "please re-run this entire script using 'sudo ./install_and_run.sh'"
fi

python3 "$PYTHON_SCRIPT"

# 6. Deactivate the virtual environment
deactivate

echo ""
echo "--- Script finished. ---"
