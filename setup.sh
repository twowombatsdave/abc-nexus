#!/bin/bash

# Check for --config flag
if [ "$1" = "--config" ] || [[ "$1" == *"config"* ]]; then
    echo "📁 --config flag detected, copying dev credentials..."

    # Check if we're in a dev-projects subdirectory
    if [[ "$PWD" == *"/dev-projects/"* ]]; then
        # Get the parent dev-projects directory
        DEV_PROJECTS_DIR=$(echo "$PWD" | sed 's|/dev-projects/.*|/dev-projects|')
        CONFIG_SOURCE="$DEV_PROJECTS_DIR/config"

        if [ -d "$CONFIG_SOURCE" ]; then
            echo "📂 Copying config from: $CONFIG_SOURCE"

            # Create local config directory if it doesn't exist
            mkdir -p config

            # Copy all files from dev-projects/config to local config
            cp -r "$CONFIG_SOURCE"/* config/ 2>/dev/null || {
                echo "⚠️  Some files may not have copied successfully"
            }

            echo "✓ Dev credentials copied to local config/"
            echo "📝 Remember to update with project-specific credentials before production"
        else
            echo "❌ Config directory not found at: $CONFIG_SOURCE"
            echo "💡 Make sure you have a 'config' folder in your dev-projects directory"
            exit 1
        fi
    else
        echo "❌ This script must be run from within a dev-projects subdirectory"
        echo "💡 Expected path: /path/to/dev-projects/your-project/"
        exit 1
    fi

    # If only config flag, exit here
    if [ "$1" = "--config" ]; then
        echo "✅ Config copy complete! Exiting."
        return 0 2>/dev/null || exit 0
    fi
fi

# Load DBT_DATASET from local secrets.json if it exists (runs on every setup.sh call)
if [ -f "config/secrets.json" ]; then
    echo "🔧 Loading DBT_DATASET from config/secrets.json..."
    DBT_DATASET=$(python3 -c "
import json
import sys
try:
    with open('config/secrets.json', 'r') as f:
        secrets = json.load(f)
    if 'strings' in secrets and 'DBT_DATASET' in secrets['strings']:
        print(secrets['strings']['DBT_DATASET'])
    else:
        print('example_dbt', file=sys.stderr)
        sys.exit(1)
except:
    print('example_dbt', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || echo "example_dbt")

    if [ "$DBT_DATASET" != "example_dbt" ]; then
        export DBT_DATASET="$DBT_DATASET"
        export DBT_SERVICE_ACCOUNT="$PWD/config/dbt_service_account.json"
        export DBT_PROFILES_DIR="$PWD/dbt/profiles"
        export DBT_PROJECT_DIR="$PWD/dbt"
        echo "✓ DBT_DATASET set to: $DBT_DATASET"
        echo "✓ DBT_SERVICE_ACCOUNT set to: $DBT_SERVICE_ACCOUNT"
        echo "✓ DBT_PROFILES_DIR set to: $DBT_PROFILES_DIR"
        echo "✓ DBT_PROJECT_DIR set to: $DBT_PROJECT_DIR"
    else
        echo "⚠️  DBT_DATASET not found in secrets.json, using default: example_dbt"
    fi
else
    echo "⚠️  config/secrets.json not found, using default DBT_DATASET: example_dbt"
fi

# Check for --save or -s flag
if [ "$1" = "--save" ] || [ "$1" = "-s" ] || [[ "$1" == *"s"* ]]; then
    echo "💾 --save/-s flag detected, saving current packages to requirements.txt..."

    # Check if we're in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "⚠️  No virtual environment detected. Activating existing venv if available..."
        if [ -d "venv" ]; then
            source venv/bin/activate
            echo "✓ Virtual environment activated"
        else
            echo "❌ No virtual environment found. Please create one first or run without -s flag."
            exit 1
        fi
    fi

    pip freeze > requirements.txt
    echo "✓ Current packages saved to requirements.txt"

    # If only save flag, return here (works for both sourced and executed scripts)
    if [ "$1" = "--save" ] || [ "$1" = "-s" ]; then
        echo "✅ Save complete! Exiting."
        return 0 2>/dev/null || exit 0
    fi
fi

# Check for --clear or -c flag
if [ "$1" = "--clear" ] || [ "$1" = "-c" ] || [[ "$1" == *"c"* ]]; then
    echo "🧹 --clear/-c flag detected, clearing requirements.txt..."
    if [ -f "requirements.txt" ]; then
        > requirements.txt  # Clear the file
        echo "✓ requirements.txt cleared"
    else
        echo "⚠️  requirements.txt not found, creating empty file"
        touch requirements.txt
    fi

    # Clear flag automatically includes new venv creation
    echo "🔄 Clearing also triggers new venv creation..."
    echo "Deleting existing virtual environment..."
    rm -rf venv
    echo "✓ Existing virtual environment removed"
fi

# Check for --new or -n flag (only if not already handled by clear)
if ([ "$1" = "--new" ] || [ "$1" = "-n" ] || [[ "$1" == *"n"* ]]) && !([ "$1" = "--clear" ] || [ "$1" = "-c" ] || [[ "$1" == *"c"* ]]); then
    echo "🔄 --new/-n flag detected, forcing clean rebuild..."
    echo "Deleting existing virtual environment..."
    rm -rf venv
    echo "✓ Existing virtual environment removed"
fi

# Check if virtual environment already exists
if [ -d "venv" ]; then
    echo "✓ Virtual environment already exists"
    echo "Activating existing virtual environment..."
    # Force deactivate any existing environment
    unset VIRTUAL_ENV
    unset PYTHONPATH
    # Remove the function if it exists
    unset -f deactivate 2>/dev/null || true
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "No virtual environment found, creating new one..."
    # Force deactivate any existing environment
    unset VIRTUAL_ENV
    unset PYTHONPATH
    unset -f deactivate 2>/dev/null || true
    # Create a new venv
    python3 -m venv venv

    # Activate the environment
    source venv/bin/activate
    echo "✓ New virtual environment created and activated"
fi

# Verify we're in the correct virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment not activated properly"
    echo "Trying to activate local venv..."
    unset VIRTUAL_ENV
    unset PYTHONPATH
    unset -f deactivate 2>/dev/null || true
    source venv/bin/activate
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "❌ Failed to activate local virtual environment"
        exit 1
    fi
fi

# Check if we're in the right environment (but don't fail if not)
if [[ "$VIRTUAL_ENV" != *"$(pwd)"* ]]; then
    echo "⚠️  Warning: Virtual environment path doesn't match current directory"
    echo "Current VIRTUAL_ENV: $VIRTUAL_ENV"
    echo "Current directory: $(pwd)"
    echo "This might cause issues, but continuing..."
fi

echo "✓ Virtual environment confirmed: $VIRTUAL_ENV"

# Install/update dependencies from requirements.txt
echo "Installing dependencies from requirements.txt..."
# Use the virtual environment's pip explicitly
if [ -f "venv/bin/pip" ]; then
    venv/bin/pip install -r requirements.txt
    echo "✓ Dependencies installed successfully"
    # Ensure dbt packages are installed on every run
    if command -v dbt >/dev/null 2>&1; then
        echo "Installing/Updating dbt packages (dbt deps)..."
        if [ -d "dbt" ]; then
            dbt deps --profiles-dir dbt/profiles --project-dir dbt || echo "⚠️  dbt deps encountered an issue"
        else
            dbt deps || echo "⚠️  dbt deps encountered an issue"
        fi
    fi
else
    echo "❌ Virtual environment pip not found at venv/bin/pip"
    echo "Trying to use system pip..."
    pip install -r requirements.txt
    echo "✓ Dependencies installed successfully (using system pip)"
    # Ensure dbt packages are installed on every run
    if command -v dbt >/dev/null 2>&1; then
        echo "Installing/Updating dbt packages (dbt deps)..."
        if [ -d "dbt" ]; then
            dbt deps --profiles-dir dbt/profiles --project-dir dbt || echo "⚠️  dbt deps encountered an issue"
        else
            dbt deps || echo "⚠️  dbt deps encountered an issue"
        fi
    fi
fi

# Show usage info if --help or -h
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --config     Copy dev credentials from dev-projects/config (exits after copy)"
    echo "  -c, --clear  Clear requirements.txt file AND create new venv"
    echo "  -n, --new    Force delete and recreate virtual environment"
    echo "  -s, --save   Save current packages to requirements.txt (exits after save)"
    echo "  -h, --help   Show this help message"
    echo ""
    echo "Combined options:"
    echo "  --config -s  Copy dev credentials AND save current packages"
    echo "  -sc, -cs     Save current packages AND clear requirements.txt (creates new venv)"
    echo "  -sn, -ns     Save current packages AND create new venv"
    echo "  -snc, -scn, -nsc, -ncs, -csn, -cns  Save, clear, AND create new venv"
    echo ""
    echo "Default behavior:"
    echo "  - Use existing venv if available"
    echo "  - Create new venv only if none exists"
    echo "  - Always install/update requirements"
fi