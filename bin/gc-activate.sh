#!/bin/bash

# Don't execute this in a subshell.  It must be sourced in order to
# cause venv activation.

# Where to find the requirements file:
requirements="$HOME/src/jma/gnucash/bin/requirements.txt"
# Where to put the venv.
venv="$HOME/.gnucash-$LOGNAME/venv"

# Activate a python virtualenv.
# Create it if necessary.
# Populate it if necessary.

if [ -d "$venv" ]; then
    . "$venv/bin/activate"
else
    read -p "No gc virtual environment exists.  Create?  " yesno
    case "$yesno" in
	yes|y|YES|Y )
	    mkdir -p "$venv"
	    virtualenv --python=python3 "$venv"
	    . "$venv/bin/activate"
	    pip install -r "$requirements"
	    ;;
	* )
	    ;;
    esac
fi
