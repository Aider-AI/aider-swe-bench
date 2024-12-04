#!/bin/bash

# Find all json files recursively in predictions directory
find ./predictions/codebuff -type f -name "*.json" | while read -r file; do
    # Extract the model_patch field and check if it's empty or null
    model_patch=$(jq -r '.model_patch' "$file")
    if [ "$model_patch" = "null" ] || [ "$model_patch" = "" ]; then
        echo "Deleting empty model_patch in: $file"
        # Get the base name without extension and directory
        base_name=$(basename "$file" .json)
        # Delete the json file
        rm "$file"
        # Delete the corresponding log file if it exists
        log_file="./logs/codebuff/${base_name}.eval.log"
        if [ -f "$log_file" ]; then
            echo "Deleting corresponding log file: $log_file"
            rm "$log_file"
        fi
    fi
done
