#!/bin/bash

# Activate the correct virtual environment
source "/home/faisal/Workspace/Dev/Personal/dictator/dictate/bin/activate"
cd "/home/faisal/Workspace/Dev/Personal/dictator"

# Use the device ID provided in the arguments (or default to 4 if that's the known working one)
# We will allow passing arguments properly
exec python -u dictate.py "$@"
