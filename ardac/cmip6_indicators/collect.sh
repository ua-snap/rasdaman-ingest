#!/bin/bash

traverse() {
    for file in "$1"/*; do
        if [ -d "$file" ]; then
            traverse "$file" 
        elif [ -f "$file" ]; then
            echo "Copying file: $file"
            cp "$file" "$destination_directory" 
        fi
    done
}

# Check if number of arguments provided is correct
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <source_directory> <destination_directory>"
    exit 1
fi

source_directory="$1"
destination_directory="$2"

# Check if source directory exists
if [ ! -d "$source_directory" ]; then
    echo "Source directory does not exist."
    exit 1
fi

# Check if destination directory exists, if not, create it
if [ ! -d "$destination_directory" ]; then
    echo "Creating destination directory: $destination_directory"
    mkdir -p "$destination_directory"
fi

# Call the traverse function
traverse "$source_directory"

echo "File copying completed."