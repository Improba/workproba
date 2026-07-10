#!/bin/bash

# Use examples: 
# ./scripts/create-tag.sh prod
# ./scripts/create-tag.sh prod major 
# ./scripts/create-tag.sh prod minor
# ./scripts/create-tag.sh prod patch

# Ensure script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script must be run with bash, not sh"
    exit 1
fi

# Exit on error in subscript
set -e

# The first argument may be: 
# - prod
# If no argument is provided, error
if [ -z "$1" ]; then
    echo "No argument provided, for example prod"
    exit 1
fi
deployType="$1"

# Print the deploy type
echo "Deploy type: $deployType"

# The second argument may be: 
# - major
# - minor
# - patch
# If no argument is provided, it is patch
if [ -z "$2" ]; then
    versionType="patch"
else
    versionType="$2"

    if [ "$versionType" != "major" ] && [ "$versionType" != "minor" ] && [ "$versionType" != "patch" ]; then
        echo "Invalid version type, must be major, minor or patch"
        exit 1
    fi
fi

echo "Version type: $versionType"

# Get script directory in a cross-platform way
scriptFolderPath="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get the version from the package.json of front and api
frontVersion=$(cat $scriptFolderPath/../front/package.json | jq -r '.version')
apiVersion=$(cat $scriptFolderPath/../api/package.json | jq -r '.version')

# Print the versions
echo "Front version: $frontVersion"
echo "API version: $apiVersion"

# If the version are not the same, exit
if [ "$frontVersion" != "$apiVersion" ]; then
    echo "Front and API versions are not the same, you need to deal with this manually"
    exit 1
fi

# If the version are the same, continue
echo "Front and API versions are the same, continuing..."

# Check the latest beginning with deployType
latestTag=$(git tag -l | grep "^${deployType}-v" | sort -V | tail -n 1)

# If the latest tag is "after" the current version (1.2.1 > 1.2.0), exit with a warning
if [ ! -z "$latestTag" ]; then
    latestVersion=$(echo $latestTag | sed "s/${deployType}-v//")
    
    # Compare versions in a cross-platform way
    frontMajor=$(echo $frontVersion | cut -d. -f1)
    frontMinor=$(echo $frontVersion | cut -d. -f2)
    frontPatch=$(echo $frontVersion | cut -d. -f3)
    
    latestMajor=$(echo $latestVersion | cut -d. -f1)
    latestMinor=$(echo $latestVersion | cut -d. -f2)
    latestPatch=$(echo $latestVersion | cut -d. -f3)
    
    isNewer=false
    if [ "$latestMajor" -gt "$frontMajor" ]; then
        isNewer=true
    elif [ "$latestMajor" -eq "$frontMajor" ] && [ "$latestMinor" -gt "$frontMinor" ]; then
        isNewer=true
    elif [ "$latestMajor" -eq "$frontMajor" ] && [ "$latestMinor" -eq "$frontMinor" ] && [ "$latestPatch" -gt "$frontPatch" ]; then
        isNewer=true
    fi
    
    if [ "$isNewer" = true ]; then
        echo "Warning: Latest tag version ($latestVersion) is newer than current version ($frontVersion)"
        echo "This might indicate that you're trying to publish an older version"
        read -p "Do you want to continue? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Increment version
if [ "$versionType" == "major" ]; then
    newVersion=$(echo $frontVersion | awk -F. '{print $1 + 1 "." 0 "." 0}')
elif [ "$versionType" == "minor" ]; then
    newVersion=$(echo $frontVersion | awk -F. '{print $1 "." $2 + 1 "." 0}')
else
    newVersion=$(echo $frontVersion | awk -F. '{print $1 "." $2 "." $3 + 1}')
fi

# Print the new version
echo "New version: $newVersion"

if [[ "$OSTYPE" == "darwin"* ]]; then
    SED_CMD="sed -i ''"
else
    SED_CMD="sed -i"
fi

$SED_CMD "s/\"version\": \"$frontVersion\"/\"version\": \"$newVersion\"/g" "$scriptFolderPath/../front/package.json"
$SED_CMD "s/\"version\": \"$frontVersion\"/\"version\": \"$newVersion\"/g" "$scriptFolderPath/../api/package.json"

# Make a version commit and push it to the remote repository
git add $scriptFolderPath/../front/package.json
git add $scriptFolderPath/../api/package.json
git commit -m "Bump version to $newVersion"
git push

# Create a new tag with format prod-vX.Y.Z
git tag ${deployType}-v$newVersion

# Push the tag to the remote repository
git push origin ${deployType}-v$newVersion

# All done
echo "All done, the CI will now run on GitHub"





