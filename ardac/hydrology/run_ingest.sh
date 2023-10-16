#!/bin/bash

source /etc/profile.d/rasdaman.sh

while true; do
    /opt/rasdaman/bin/wcst_import.sh -c 0 ingest.json 2>&1   

    # Get the exit status of the last command
    exit_status=$?

    # Check if the exit status is 0
    if [ $exit_status -eq 0 ]; then
        echo "Command executed successfully."
        break  # Exit the loop
    else
        echo "Command failed with exit status $exit_status. Retrying..."
        sleep 5  # Add a delay before retrying
    fi
done