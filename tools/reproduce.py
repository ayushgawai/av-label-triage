#!/usr/bin/env python3
"""Run CPU-only test and fixture gates without external data or models."""
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    subprocess.run([sys.executable,'-m','pytest','-q'],check=True)
    subprocess.run([sys.executable,'tools/audit_simulation.py'],check=True)
    from avtriage.fixture import demo
    with tempfile.TemporaryDirectory() as d:
        print('Fixture:', demo(Path(d)))


if __name__=='__main__': main()
