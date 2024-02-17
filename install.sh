#!/bin/bash

# Copy scripts to my bin/ directory so that I find them.
# Note that this assumes that $cwd is where this script lives.

(cd bin; cp gc_*py gc-*.sh $HOME/bin/)

# Clean up old scripts.  These lines can be removed once they've been
# here for a while.
rm -f $HOME/bin/gc-make-ledger.sh
