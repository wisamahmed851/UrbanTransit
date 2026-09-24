#!/usr/bin/env bash
# Phase 1 pipeline run (one WSL session so the distro stays up)
cd /mnt/d/Techwise_2026 && source ~/venvs/urbantransit/bin/activate
ts=$(date +%Y%m%d_%H%M%S); L=reports/processing_logs
step() { echo "=== $1 $(date +%H:%M:%S)"; }
step gen_full;      { time python -m data_generator.generate --mode full ; } > $L/generate_full_$ts.log 2>&1; echo "exit=$?"; tail -n 1 $L/generate_full_$ts.log
step validate_full; { time python -m data_generator.validate_dataset --mode full ; } > $L/validate_full_$ts.log 2>&1; echo "exit=$?"; grep -E "FAIL|RESULT" $L/validate_full_$ts.log
step stats_full;    { time python -m data_generator.dataset_stats --mode full ; } > $L/dataset_stats_full_$ts.log 2>&1; echo "exit=$?"
step gen_hidden;    python -m data_generator.generate --mode hidden_like > $L/generate_hidden_like_$ts.log 2>&1; echo "exit=$?"; tail -n 1 $L/generate_hidden_like_$ts.log
step validate_hidden; python -m data_generator.validate_dataset --mode hidden_like > $L/validate_hidden_like_$ts.log 2>&1; echo "exit=$?"; grep -E "FAIL|RESULT" $L/validate_hidden_like_$ts.log
step determinism_full;   { time python -m data_generator.determinism_check --mode full --tmp ~/det_check ; } > $L/determinism_full_$ts.log 2>&1; echo "exit=$?"; grep -E "Same seed|manifest identical|DETERMINISM" $L/determinism_full_$ts.log
step determinism_sample; python -m data_generator.determinism_check --mode sample --tmp ~/det_check_s --control-seed 43 > $L/determinism_sample_$ts.log 2>&1; echo "exit=$?"; grep -E "Same seed|manifest identical|Control seed|DETERMINISM" $L/determinism_sample_$ts.log
step done
