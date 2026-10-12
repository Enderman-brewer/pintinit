#!/bin/bash

for cmd in busybox python gcc qemu-system-x86_64; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: Required command '$cmd' is not installed."
        exit 1
    fi
done
