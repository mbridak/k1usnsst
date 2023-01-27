#!/bin/bash
pip uninstall -y k1usnsst
rm dist/*
python3 -m build
python3 -m twine upload dist/*
