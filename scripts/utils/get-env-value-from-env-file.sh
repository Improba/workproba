#!/bin/sh

# Check if exactly three arguments are provided
if [ $# -ne 2 ]; then
  echo "Usage: $0 <path-to-env-file> <env-key>"
  exit 1
fi

# Specify the path to the .env file
ENV_FILE_PATH=$1
# Specify the key to search for in the .env file
ENV_KEY=$2

# Check if the .env file exists
if [ ! -f "$ENV_FILE_PATH" ]; then
  echo "Error: .env file not found."
  exit 1
fi

# Read the ENV_KEY value from the .env file
app_name=$(grep "^$ENV_KEY=" "$ENV_FILE_PATH" | cut -d'=' -f2)

# Check if ENV_KEY was found
if [ -z "$app_name" ]; then
  echo "$ENV_KEY not defined in the .env file."
  exit 1
fi

# Output the ENV_KEY value
echo "$app_name"
