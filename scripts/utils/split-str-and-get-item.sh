#!/bin/bash

# Check if exactly three arguments are provided
if [ $# -ne 3 ]; then
  echo "Usage: $0 <str> <delimiter> <index>"
  exit 1
fi

# main string
str="$1"

# delimiter string
delimiter="$2"

# index of the substring to be extracted
INDEX="$3"

#length of main string
strLen=${#str}
#length of delimiter string
dLen=${#delimiter}

#iterator for length of string
i=0
#length tracker for ongoing substring
wordLen=0
#starting position for ongoing substring
strP=0

array=()
while [ $i -lt $strLen ]; do
    if [ $delimiter == ${str:$i:$dLen} ]; then
        array+=(${str:strP:$wordLen})
        strP=$(( i + dLen ))
        wordLen=0
        i=$(( i + dLen ))
    fi
    i=$(( i + 1 ))
    wordLen=$(( wordLen + 1 ))
done
array+=(${str:strP:$wordLen})

# declare -p array

echo ${array[$INDEX]}
