#!/bin/sh

# Exit on error in subscript
set -e

# Current script folder path
currentFolderPath=$( dirname -- "$( readlink -f -- "$0"; )"; )
# Go into the current script folder
cd $currentFolderPath

# Import the colors variables
. ./colors.sh

# Default arg1 value
args=""
# Give arg1 the value of the first argument if any
if [ -z "$1" ]; then
  # No argument supplied: error
  echo "Error: No argument supplied"
  exit 1
else
  # Put all the args in a string: sh compose.sh arg1 arg2 -> args="arg1 arg2"
  args="$*"
fi

if [ "$args" = "up" ]; then
  echo "WARNING \"up\" cannot be used without \"-d\". Running with \"up -d\""
  args="up -d"
fi

if [ "$args" = "console" ]; then
  echo "ERROR: console can only be used from one of the subproject folders (front, api, code-generator/back, code-generator/front)"
  exit 1
fi

# Start the api
echo "Workproba API..."
# Go in the api folder
cd $currentFolderPath/../api/docker
# echo docker-compose up in green color
echo -e "${BLUE}sh api/docker/compose.sh $args${NC}"
# Start the api
sh compose.sh $args
# Go back to root folder
cd $currentFolderPath

# Start the front
echo "Workproba frontend..."
# Go in the front folder
cd $currentFolderPath/../front/docker
# echo docker-compose up in green color
echo -e "${BLUE}sh api/docker/compose.sh $args${NC}"
# Start the front
sh compose.sh $args
# Go back to root folder
cd $currentFolderPath