#!/bin/bash

# First argument is the source directory, typically the git repository.
#src_dir="$1"
src_dir="$HOME/src/jma/gnucash/bin"
# Second argument is the destination directory, where to create the virtualenv.
#dst_dir="$2"
dst_dir="."

cd "$dst_dir"
virtualenv --python=python3 venv
. venv/bin/activate
pip install -r "$src_dir/requirements.txt"
