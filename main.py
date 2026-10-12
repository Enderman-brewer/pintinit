import subprocess

cmd = [
    ["mount", "-t", "sysfs", "sysfs", "/sys"],
    ["mount", "-t", "sysfs", "sys", "/mnt/sys"],
    ["mount", "--rbind", "/dev", "/mnt/dev"]
]

for i in cmd:
    try:
        result = subprocess.run(
            i,
            capture_output=True,
            text=True,
            check=True
        )
        print("Successfully mounted /sys")
    except subprocess.CalledProcessError as e:
        print(f"Mount failed with code {e.returncode}: {e.stderr}")
