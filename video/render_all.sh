#!/bin/bash
# Render every shot in order; resumable (skips frames already on disk).
export WP_OUT=${WP_OUT:-/tmp/wp_frames}
PY=${PY:-python3}
cd "$(dirname "$0")"
for s in ${SHOTS:-s1 s2 s3 s4 s5 s6 s7 s8 s9}; do
  $PY shots.py $s full 2>&1 | grep --line-buffered -E "FRAME|Traceback|Error:"
done
echo ALL_DONE
