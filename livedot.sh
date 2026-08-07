#!/bin/bash
# Livedot startup wrapper script

# Resolve the absolute path of the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the python script using the virtual environment's python interpreter
"$DIR/venv/bin/python3" "$DIR/livedot.py" "$@"
