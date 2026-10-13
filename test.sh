
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ROOT="$PWD/fakefs"
DIST="$PWD/build/main.dist"
IMAGE="$PWD/build/pintinit-initramfs.img"

# Clean and prepare initramfs
rm -rf "$ROOT"

mkdir -p \
    "$ROOT/bin" \
    "$ROOT/sbin" \
    "$ROOT/usr/bin" \
    "$ROOT/usr/sbin" \
    "$ROOT/usr/lib" \
    "$ROOT/lib64" \
    "$ROOT/etc/pintinit" \
    "$ROOT/dev" \
    "$ROOT/proc" \
    "$ROOT/sys" \
    "$ROOT/mnt" \
    "$ROOT/run" \
    "$ROOT/tmp" \
    "$ROOT/root" \
    "$ROOT/var/log" \
    "$ROOT/opt/pintinit"

chmod 1777 "$ROOT/tmp"

# Basic operating system identity
cat > "$ROOT/etc/os-release" <<'EOF'
NAME="Pintinit"
PRETTY_NAME="Pintinit 0.1 (Fake)"
ID=pintinit
VERSION_ID="0.1"
EOF

# Minimal account database
cat > "$ROOT/etc/passwd" <<'EOF'
root:x:0:0:root:/root:/bin/sh
EOF

cat > "$ROOT/etc/group" <<'EOF'
root:x:0:
tty:x:5:
EOF

cat > "$ROOT/etc/shadow" <<'EOF'
root::0:0:99999:7:::
EOF

chmod 600 "$ROOT/etc/shadow"

# Copy Nuitka distribution
if [[ ! -x "$DIST/main.bin" ]]; then
    echo "ERROR: Nuitka binary missing: $DIST/main.bin" >&2
    exit 1
fi

cp -a "$DIST/." "$ROOT/opt/pintinit/"

# Install BusyBox
BUSYBOX="$(command -v busybox)"

install -Dm755 "$BUSYBOX" "$ROOT/bin/busybox"

for cmd in \
    sh mount mkdir ls cat echo \
    poweroff reboot ps kill sleep \
    id uname dmesg
do
    if "$BUSYBOX" --list | grep -qx "$cmd"; then
        ln -sf busybox "$ROOT/bin/$cmd"
    fi
done

# Ensure /bin/sh exists
if [[ ! -e "$ROOT/bin/sh" ]]; then
    echo "ERROR: BusyBox lacks sh applet" >&2
    exit 1
fi

find_library() {
    local name="$1"

    ldconfig -p | awk -v name="$name" '
        $1 == name && /x86-64/ && !found {
            path = $NF
            found = 1
        }
        END {
            if (found) print path
        }
    '
}

# Track visited ELF files
declare -A VISITED=()

# Copy a file into the initramfs, preserving its
# absolute path and following host symlinks.
copy_file() {
    local source="$1"
    local destination="$ROOT$source"

    if [[ ! -f "$source" ]]; then
        echo "ERROR: Missing file: $source" >&2
        exit 1
    fi

    mkdir -p "$(dirname "$destination")"
    cp -L "$source" "$destination"
}

# Recursively copy ELF dependencies.
copy_deps() {
    local binary="$1"
    local resolved
    local interpreter
    local lib
    local path

    resolved="$(readlink -f "$binary")"

    if [[ -n "${VISITED[$resolved]:-}" ]]; then
        return
    fi

    VISITED["$resolved"]=1

    # Ignore non-ELF files
    if ! readelf -h "$resolved" >/dev/null 2>&1; then
        return
    fi

    # Copy ELF interpreter
    interpreter="$(
        readelf -l "$resolved" 2>/dev/null |
        sed -n 's/.*Requesting program interpreter: \(.*\)]/\1/p'
    )"

    if [[ -n "$interpreter" ]]; then
        copy_file "$interpreter"
        copy_deps "$interpreter"
    fi

    # Copy shared library dependencies recursively
    while IFS= read -r lib; do
        [[ -n "$lib" ]] || continue

        path="$(find_library "$lib")"

        if [[ -z "$path" ]]; then
            echo "ERROR: Cannot locate library $lib" >&2
            echo "Required by: $resolved" >&2
            exit 1
        fi

        copy_file "$path"
        copy_deps "$path"

    done < <(
        readelf -d "$resolved" 2>/dev/null |
        sed -n 's/.*Shared library: \[\(.*\)\]/\1/p'
    )
}

# Copy dependencies for main executables
copy_deps "$DIST/main.bin"
copy_deps "$BUSYBOX"

# Copy dependencies of every Nuitka ELF file
while IFS= read -r -d '' file; do
    copy_deps "$file"
done < <(find "$DIST" -type f -print0)

# Install agetty and login
AGETTY="$(command -v agetty)"
LOGIN="$(command -v login)"

install -Dm755 "$AGETTY" "$ROOT/sbin/agetty"
install -Dm755 "$LOGIN" "$ROOT/bin/login"

copy_deps "$AGETTY"
copy_deps "$LOGIN"

# Make standard Arch-style library paths available
ln -sfn usr/lib "$ROOT/lib"
ln -sfn usr/lib "$ROOT/lib64"

# Explicitly include libgcc_s, which can be
# dynamically loaded rather than directly linked.
GCC_LIB="$(find_library libgcc_s.so.1)"

if [[ -n "$GCC_LIB" ]]; then
    copy_file "$GCC_LIB"
    copy_deps "$GCC_LIB"
else
    echo "WARNING: libgcc_s.so.1 not found" >&2
fi

# Copy basic NSS configuration
cat > "$ROOT/etc/nsswitch.conf" <<'EOF'
passwd: files
group: files
shadow: files
hosts: files dns
EOF

# Include common dynamically loaded NSS libraries
for lib in libnss_files.so.2 libnss_dns.so.2; do
    path="$(find_library "$lib")"

    if [[ -n "$path" ]]; then
        copy_file "$path"
        copy_deps "$path"
    fi
done

# Include PAM configuration if installed
if [[ -d /etc/pam.d ]]; then
    mkdir -p "$ROOT/etc/pam.d"
    cp -a /etc/pam.d/. "$ROOT/etc/pam.d/"
fi

if [[ -f /etc/security/limits.conf ]]; then
    mkdir -p "$ROOT/etc/security"
    cp /etc/security/limits.conf "$ROOT/etc/security/"
fi

# PAM modules may be loaded using dlopen(), so
# readelf alone will not discover them.
if [[ -d /usr/lib/security ]]; then
    mkdir -p "$ROOT/usr/lib/security"

    while IFS= read -r -d '' module; do
        cp -L "$module" \
            "$ROOT/usr/lib/security/$(basename "$module")"
        copy_deps "$module"
    done < <(
        find /usr/lib/security \
            -maxdepth 1 \
            -type f -name '*.so' -print0
    )
fi

cat > "$ROOT/etc/pam.d/login" <<'EOF'
auth       sufficient   pam_permit.so
account    sufficient   pam_permit.so
password   sufficient   pam_permit.so
session    sufficient   pam_permit.so
EOF

# Copy the PintInit configuration
if [[ ! -f config-skel.py ]]; then
    echo "ERROR: config-skel.py is missing" >&2
    exit 1
fi

cp config-skel.py "$ROOT/etc/pintinit/config.py"

# Create /init
cat > "$ROOT/init" <<'EOF'
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

chmod +x "$ROOT/init"

# Validate required executables
for executable in \
    /init \
    /bin/sh \
    /bin/login \
    /sbin/agetty \
    /opt/pintinit/main.bin
do
    if [[ ! -e "$ROOT$executable" ]]; then
        echo "ERROR: Missing $executable" >&2
        exit 1
    fi
done

# Build initramfs
echo "Packaging PintInit initramfs..."

(
    cd "$ROOT"
    find . -print0 |
        cpio --null -o -H newc --quiet |
        gzip -1
) > "$IMAGE"

echo "Initramfs size: $(du -h "$IMAGE" | cut -f1)"
echo "Starting PintInit VM..."

# Boot virtual machine
exec qemu-system-x86_64 \
    -m 512M \
    -kernel /boot/vmlinuz-linux \
    -initrd "$IMAGE" \
    -append "console=ttyS0 rdinit=/init loglevel=4" \
    -nographic \
    -cpu max \
    -no-reboot
