#!/bin/bash

# Enable error handling (but don't exit on errors, handle them explicitly)
set +e

# Check if repo name argument is provided
if [ -z "$1" ]; then
    echo "Error: Repository name is required"
    echo "Usage: ./tw-init.sh <repo-name>"
    exit 1
fi

REPO_NAME="$1"
ORG_NAME="twowombatsgit"
FULL_REPO_NAME="${ORG_NAME}/${REPO_NAME}"

# Change to dev-projects directory to keep all projects organized
echo "Changing to dev-projects directory..."
cd /home/adam/dev-projects || {
    echo "Error: Failed to change to dev-projects directory"
    read -p "Press Enter to continue..."  # Keep terminal open
    exit 1
}

# Check if repository already exists
echo "Checking if repository '$FULL_REPO_NAME' already exists..."
if gh repo view "$FULL_REPO_NAME" >/dev/null 2>&1; then
    echo "Repository '$FULL_REPO_NAME' already exists. Cloning existing repository..."
    gh repo clone "$FULL_REPO_NAME"

    # Check if clone was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to clone existing repository '$FULL_REPO_NAME'"
        read -p "Press Enter to continue..."  # Keep terminal open
        exit 1
    fi
else
    # Create the repository from template and clone it
    echo "Creating repository '$FULL_REPO_NAME' from template twowombatsgit/tw-init..."
    echo "Running: gh repo create $FULL_REPO_NAME --template twowombatsgit/tw-init --private --clone"
    gh repo create "$FULL_REPO_NAME" --template twowombatsgit/tw-init --private --clone 2>&1

    # Check if repo creation was successful
    if [ $? -ne 0 ]; then
        echo ""
        echo "Error: Failed to create repository '$FULL_REPO_NAME'"
        echo "This might be due to permissions or the --owner flag syntax."
        echo "Please check the error message above."
        read -p "Press Enter to continue..."  # Keep terminal open
        exit 1
    fi
fi

# Change into the new repository directory
echo "Changing directory to '$REPO_NAME'..."
cd "$REPO_NAME" || {
    echo "Error: Failed to change directory to '$REPO_NAME'"
    read -p "Press Enter to continue..."  # Keep terminal open
    exit 1
}

# Open in Cursor
echo "Opening '$REPO_NAME' in Cursor..."
if ! command -v cursor &> /dev/null; then
    echo "Warning: 'cursor' command not found. Skipping Cursor launch."
else
    cursor . || {
        echo "Warning: Failed to open Cursor. Continuing anyway..."
    }
fi

# Run setup.sh with --config flag
echo "Running setup.sh --config..."
if [ -f "setup.sh" ]; then
    source setup.sh --config
    if [ $? -ne 0 ]; then
        echo "Warning: setup.sh returned an error code"
    fi
else
    echo "Error: setup.sh not found in '$REPO_NAME'"
    read -p "Press Enter to continue..."  # Keep terminal open
    exit 1
fi

echo "Setup complete!"
echo "You are now in: $(pwd)"

