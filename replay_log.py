#!/usr/bin/env python3
"""Replay a saved NIFTy log line by line, to develop the GUI without running NIFTy.

  python nifty_gui.py -- python replay_log.py run.log --delay 0.05
"""
import argparse
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("logfile")
ap.add_argument("--delay", type=float, default=0.05, help="seconds between lines")
args = ap.parse_args()

with open(args.logfile, encoding="utf-8") as f:
    for line in f:
        sys.stdout.write(line)
        sys.stdout.flush()
        time.sleep(args.delay)