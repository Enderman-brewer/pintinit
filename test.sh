#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

ROOT="$PWD/fakefs"
DIST="$PWD/build/main.dist"

rm -rf "$ROOT"
mkdir -p "$ROOT"/{bin,dev,proc,sys,mnt,run,tmp,usr/lib,lib64,opt/pintinit}

# Copy Nuitka distribution
cp -a "$DIST/." "$ROOT/opt/pintinit/"

# Install BusyBox utilities
cp /usr/bin/busybox "$ROOT/bin/busybox"

for cmd in sh mount mkdir ls cat echo poweroff reboot; do
    ln -s busybox "$ROOT/bin/$cmd"
done

# Copy ELF dependencies recursively, preserving their paths.
copy_deps() {
    local binary="$1"
    local lib path interpreter

    # Copy the ELF interpreter, if present.
    interpreter=$(readelf -l "$binary" 2>/dev/null |
        sed -n 's/.*Requesting program interpreter: \(.*\)]/\1/p')

    if [[ -n "$interpreter" ]]; then
        mkdir -p "$ROOT$(dirname "$interpreter")"
        cp -L "$interpreter" "$ROOT$interpreter"
    fi

    # Read direct shared-library dependencies.
    while IFS= read -r lib; do
        path=$(ldconfig -p | awk -v name="$lib" '
            $1 == name && /x86-64/ && !found {
                path = $NF
                found = 1
            }
            END {
                if (found) print path
            }
        ')

        if [[ -z "$path" ]]; then
            echo "ERROR: Cannot locate $lib" >&2
            exit 1
        fi

        mkdir -p "$ROOT$(dirname "$path")"
        cp -L "$path" "$ROOT$path"
    done < <(
        readelf -d "$binary" 2>/dev/null |
        sed -n 's/.*Shared library: \[\(.*\)\]/\1/p'
    )
}

copy_deps "$DIST/main.bin"
copy_deps /usr/bin/busybox

# Include dependencies of bundled Nuitka shared objects.
while IFS= read -r -d '' lib; do
    copy_deps "$lib"
done < <(find "$DIST" -type f -name '*.so*' -perm /111 -print0)

cat > "$ROOT/init" <<'EOF'
#!/bin/sh
export PATH=/bin:/usr/bin:/sbin:/usr/sbin

mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys

exec /opt/pintinit/main.bin
EOF

chmod +x "$ROOT/init"

# Package initramfs
(
    cd "$ROOT"
    find . -print0 | cpio --null -o -H newc --quiet | gzip -1
) > "$PWD/build/pintinit-initramfs.img"

# Boot virtual machine
exec qemu-system-x86_64 \
    -m 512M \
    -kernel /boot/vmlinuz-linux \
    -initrd build/pintinit-initramfs.img \
    -append "console=ttyS0 rdinit=/init loglevel=4" \
    -nographic \
    -cpu max \
    -no-reboot