#!/bin/sh

# Exit on error in subscript
set -e

# Current script folder path
currentFolderPath=$( dirname -- "$( readlink -f -- "$0"; )"; )
# Go into the current script folder
cd $currentFolderPath

# Env setup
envFiles="--env-file ./../.env"

# Default arg1 value
args="up -d"
# Give arg1 the value of the first argument if any
if [ -z "$1" ]; then
  # No argument supplied: up -d is assumed
  :
else
  # Put all the args in a string: sh compose.sh arg1 arg2 -> args="arg1 arg2"
  args="$*"
fi

# To avoid warning
export DOCKER_DEV=""

# -------------------------------------------------------
# Special case: If the first argument is "console" we open a console
# -------------------------------------------------------
if [ "$args" = "console" ]; then
  # Cannot use console in production mode
  if [ "$COMPOSE_MODE" = "production" ]; then
    # Inform the user
    echo "ERROR: You can't use \"compose.sh console\" in production mode"
    # Exit with error
    exit 1
  fi

  # Set the environment variable to true
  # This is used in the docker-compose.dev.yml file
  # to determine if the container is running in development mode
  export DOCKER_DEV=true

  # Start the containers in detached mode, taking into account the DOCKER_DEV environment variable
  docker compose ${envFiles} -f ./docker-compose.dev.yml up -d

  # Execute the bash command in the API dev container to open a console.
  docker compose ${envFiles} -f ./docker-compose.dev.yml exec workproba-api-dev bash || true

  # When the terminal is closed, stop the containers
  docker compose ${envFiles} -f ./docker-compose.dev.yml down

# -------------------------------------------------------
# Normal case: We put the arguments behing the docker compose command
# -------------------------------------------------------
else
  composeYmlFile="./docker-compose.dev.yml"
  if [ "$COMPOSE_MODE" = "production" ]; then
    composeYmlFile="./docker-compose.yml"
  fi

  # Run docker compose including two .env files
  docker compose ${envFiles} -f $composeYmlFile $args
fi
