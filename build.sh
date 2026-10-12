#!/bin/bash
set -e

python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 -m nuitka \
    --mode=standalone \
    --static-libpython=yes \
    --output-dir=build \
    main.py