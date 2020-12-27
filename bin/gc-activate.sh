#!/bin/bash

# Don't execute this in a subshell.  It must be sourced in order to
# cause venv activation.

# Where to find the requirements file:
requirements="$HOME/src/jma/gnucash/bin/requirements.txt"
# Cache directory.
export _gc__cache="$HOME/.gnucash-$LOGNAME/"
# Where to put the venv.
venv="$_gc__cache/venv"

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

# Provide quick links to favourite gnucash files.
# These are simple env variables because an array wouldn't export properly.
# Cf. https://stackoverflow.com/a/21941473/833300
_gc__tn_dir="$HOME/work/startup/transport-nantes/finances"
_gc__nmla_dir="$HOME/work/startup/ML-meetup/compta/gnucash"

export _gc__tn="$_gc__tn_dir/gnucash/transport-nantes.gnucash"
export _gc__nmla="$_gc__nmla_dir/nmla.gnucash"
export _gc__perso="$HOME/work/finance/gnucash/current/compta-perso.gnucash"
export _gc__p="$HOME/work/finance/gnucash/current/compta-perso.gnucash"
