#!/bin/bash
pip uninstall -y k1usnsst
rm dist/*
python3 -m build
pip install -e .

