#!/bin/bash

# Get the current directory's path
current_dir=$(pwd)

# Extract the parent directory's path
parent_dir=$(dirname "$current_dir")

# Extract the name of the parent directory
parent_name=$(basename "$parent_dir")

# Convert the name to lowercase and replace spaces with hyphens
formatted_name=$(echo "$parent_name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

# Output the formatted name
echo "$formatted_name"
