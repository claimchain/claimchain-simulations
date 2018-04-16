#!/bin/bash

NPROC=${NPROC:=4}

PUBLIC_BREAKPOINT_INDEX=5
BREAKPOINTS_FILE=scripts/breakpoints.txt
PUBLIC_BREAKPOINT="$(head -n $PUBLIC_BREAKPOINT_INDEX $BREAKPOINTS_FILE | tail -1)"

OUTPUT_DIR=data/reports
PRIVATE_OUT_PREFIX=private_claimchain_report_noopt
PUBLIC_OUT_PREFIX=public_claimchain_report_noopt

# Run private sims in parallel.
cat $BREAKPOINTS_FILE | \
    parallel -j $NPROC \
    python scripts/run_simulation.py \
        --introduction_policy=implicit_cc \
        --log_offset {} \
        --output $OUTPUT_DIR/$PRIVATE_OUT_PREFIX-{}.pkl

# Run single public sim in one of the chunks.
python scripts/run_simulation.py \
    --introduction_policy=public_contacts \
    --log_offset $PUBLIC_BREAKPOINT \
    --output $OUTPUT_DIR/$PUBLIC_OUT_PREFIX-$PUBLIC_BREAKPOINT.pkl
