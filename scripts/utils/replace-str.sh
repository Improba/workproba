#!/bin/sh

# Usage:
# sh replace-str.sh <file> <toBeReplaced> <toReplaceWith>

# Check if exactly three arguments are provided
if [ $# -ne 3 ]; then
  echo "Usage: $0 <file> <toBeReplaced> <toReplaceWith>"
  exit 1
fi

# Assigning arguments to variables for better readability
FILE="$1"
SEARCH="$2"
REPLACE="$3"

# Check if the file exists
if [ ! -f "$FILE" ]; then
  echo "Error: File does not exist."
  exit 1
fi

# Detect the operating system to set the sed in-place edit option
OSTYPE=$(uname)
if [ "$OSTYPE" = "Darwin" ]; then
    # macOS requires an empty string argument with -i, passed as two separate parts
    SED_INPLACE_FLAG="-i ''"
else
    # Linux does not require an empty string argument
    SED_INPLACE_FLAG="-i"
fi

# Function to escape special characters in the search and replace strings
escape_string() {
  echo "$1" | sed 's/[&/\]/\\&/g; s/\x27/\\&/g; s/"/\\"/g'
}

# Escaping special characters in the strings
ESCAPED_SEARCH=$(escape_string "$SEARCH")
ESCAPED_REPLACE=$(escape_string "$REPLACE")

# Using sed to replace all occurrences of the search string with the replacement string
sed $SED_INPLACE_FLAG "s/$ESCAPED_SEARCH/$ESCAPED_REPLACE/g" "$FILE"
