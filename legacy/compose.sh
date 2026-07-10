#!/bin/sh

# Exit on error in subscript
set -e

if [ "$COMPOSE_MODE" = "production" ]; then
  # Inform the user
  echo "WARNING: The script is running in production mode"
fi

# Default arg1 value
args=""
# Give arg1 the value of the first argument if any
if [ -z "$1" ]; then
  # No argument supplied: error
  echo "Error: No argument supplied. Use: init, up, down, up --build, up -d, etc."
  # Exit with an error
  exit 1
else
  # Put all the args in a string: sh compose.sh arg1 arg2 -> args="arg1 arg2"
  args="$*"
fi

# Special bash if init is the first argument
if [ "$args" = "init" ]; then
  # Run the init.sh script
  bash ./scripts/init.sh
# Normal case, we put the arguments behind the docker compose command
else
  # Run the compose-all.sh script
  bash ./scripts/compose-all.sh $args
fi
