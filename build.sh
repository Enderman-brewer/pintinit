#!/bin/bash
set -e

cd "$(dirname "$0")"
DIST="$PWD/build/main.dist"
DIST_CTL="$PWD/build_ctl/mainctl.dist/"

python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 -m nuitka \
    --mode=standalone \
    --static-libpython=yes \
    --output-dir=build \
    main.py

venv/bin/python3 -m nuitka \
    --mode=standalone \
    --static-libpython=yes \
    --output-dir=build_ctl \
    --output-filename=pintinitctl \
    mainctl.py


rm -rf final_dist
mkdir -p final_dist
mkdir -p final_dist/opt
mkdir -p final_dist/sbin
mkdir -p final_dist/etc/pintinit

cp -a $DIST/. final_dist/opt/pintinit/
cp -a $DIST_CTL/. final_dist/sbin/
cp config-skel.py final_dist/etc/pintinit/config.py

cat > "final_dist/sbin/init" <<'EOF'
#!/bin/sh

export PATH=/bin:/sbin:/usr/bin:/usr/sbin
export HOME=/root
export TERM=linux

mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys

mkdir -p /dev/pts
mount -t devpts devpts /dev/pts

exec /opt/pintinit/main.bin
EOF

chmod +x "final_dist/sbin/init"