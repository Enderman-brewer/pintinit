import time
START_TIME = time.perf_counter()
import subprocess
import os
import sys
import platform
from typing import TypedDict

service_list = {}
failed_list: list = []

def time_since_start():
    timesince = time.perf_counter() - START_TIME
    return f"{timesince:.5f}"

class Colour:
    # Reset
    RESET = "\033[0m"

    # Text styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    STRIKETHROUGH = "\033[9m"

    # Standard foreground colours
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colours
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Standard background colours
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Bright background colours
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"

    # Extended colour support
    @staticmethod
    def fg256(number):
        return f"\033[38;5;{number}m"

    @staticmethod
    def bg256(number):
        return f"\033[48;5;{number}m"

    @staticmethod
    def rgb(r, g, b):
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def bg_rgb(r, g, b):
        return f"\033[48;2;{r};{g};{b}m"

# Get the current process ID (PID)
current_pid = os.getpid()

# Get the parent process ID (PPID)
parent_pid = os.getppid()
print("=" * 10)
print(f"[{time_since_start()}] Current PID: {current_pid}")
print(f"[{time_since_start()}] Parent PID: {parent_pid}")
print("=" * 10)
if current_pid != 1 or parent_pid != 0:
    print("Must be started as PID 1.")
    sys.exit(1)

class InvalidServiceError(Exception):
    pass

class ServiceInfo(TypedDict):
    name: str
    status: int | None
    pid: int
    crashed: bool

def get_service(service_name: str, allow_graceful_exit: bool = False) -> ServiceInfo:
    process = service_list[service_name]
    status = process.poll()
    pid = process.pid
    if allow_graceful_exit and status == 0:
        crashed = False
    elif status is None:
        crashed = False
    else:
        crashed = True

    return {"name": service_name, "status": status, "pid": pid, "crashed": crashed}
    

def start_service(service_name: str, command: list[str], oneshot_game: bool = False):
    global service_list, failed_list
    if not service_name or not command:
        raise InvalidServiceError("Incorrect usage")
    if service_name in service_list:
        raise InvalidServiceError("Service already exists")
    process = subprocess.Popen(command)
    service_list[service_name] = process
    time.sleep(0.1)
    status = get_service(service_name)
    if status["crashed"]:
        if not (service_name in failed_list):
            failed_list = failed_list + [service_name]
    else:
        if service_name in failed_list:
            failed_list.remove(service_name)
    
        

def mount(command):
    mount_point = command[-1]
    print(f"Mounting: {mount_point}")

    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"[{time_since_start()}] Successfully mounted {mount_point}")
    except subprocess.CalledProcessError as error:
        print(f"[{time_since_start()}] Mount failed with code {error.returncode}: {error.stderr}")

try:
    os_info = platform.freedesktop_os_release()
    pretty_name = os_info.get("PRETTY_NAME", "Linux")
except FileNotFoundError:
    pretty_name = "Linux (Unknown)"

print(f"[{time_since_start()}] Welcome to {Colour.BOLD}{Colour.CYAN}{pretty_name}{Colour.RESET}!")
print(f"[{time_since_start()}] The system would like permission to get permission to start")
print(f"Would you like to start the system? {Colour.RED}[y/N]{Colour.RESET}")
time.sleep(0.2)
print(f"[{time_since_start()}] Fuck it, I know the answer...")
while True:
    time.sleep(3600)
    print(f"[{time_since_start()}] Slept for 1 hour, sleeping again.")