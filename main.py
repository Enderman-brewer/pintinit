import time
START_TIME = time.perf_counter()
import subprocess
import os
import sys
import platform
from typing import TypedDict
import traceback
import builtins
import json
import socket
import ctypes
import signal

libc = ctypes.CDLL(None)
service_list = {}
failed_list = {}
pid_to_service = {}   # pid -> service name, for children we started
exit_status = {}      # service name -> exit code, None while running
booted = False

# Linux reboot magic constants
_MAGIC1 = 0xfee1dead
_MAGIC2 = 0x28121969

# Action commands
_CMD_RESTART = 0x01234567
_CMD_POWER_OFF = 0x4321fedc

builtinprint = builtins.print



SOCKET_PATH = "/run/pintinit.sock"

def setup_command_socket():
    os.makedirs("/run", exist_ok=True)

    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    server.setblocking(False)
    return server

def get_commands(server) -> list[list[str]]:
    commands = []

    while True:
        try:
            data = server.recv(65535)
        except BlockingIOError:
            break

        try:
            command = json.loads(data)
            if isinstance(command, list) and all(isinstance(x, str) for x in command):
                commands.append(command)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    return commands


def print(*args, sep=" ", end="\n", flush=False):
    builtinprint(*args, sep=sep, end=end, flush=flush)

    try:
        with open("/dev/tty1", "w") as tty:
            builtinprint(*args, sep=sep, end=end, file=tty, flush=flush)
    except OSError:
        pass
    try:
        with open("/dev/tty8", "w") as tty:
            builtinprint(*args, sep=sep, end=end, file=tty, flush=flush)
    except OSError:
        pass

LOG_FILE = "/var/log/pintinit.log"
LOG_TTY = "/dev/tty8"

_log_fds = []  # open once, reused on every call

def _open_log_targets():
    for path, flags in (
        (LOG_TTY, os.O_WRONLY | os.O_NOCTTY),              # don't make tty8 our controlling terminal
        (LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND),
    ):
        try:
            _log_fds.append(os.open(path, flags, 0o644))
        except OSError:
            pass  # target missing or unwritable: skip it, keep booting

def log(*values, sep=" ", end="\n"):
    if not _log_fds:
        _open_log_targets()
    text = sep.join(str(v) for v in values) + end
    data = text.encode()
    for fd in _log_fds:
        try:
            os.write(fd, data)
        except OSError:
            pass  # one bad target shouldn't stop the others

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
msg = ("=" * 10) + "\n" + \
f"[{time_since_start()}] Current PID: {current_pid}" + "\n" + \
f"[{time_since_start()}] Parent PID: {parent_pid}" + "\n" + \
("=" * 10)
print(msg)
if current_pid != 1 or parent_pid != 0:
    print("Must be started as PID 1.")
    sys.exit(1)

print(f"[{time_since_start()}] Kernel time is: {time.clock_gettime(time.CLOCK_BOOTTIME)}")
print(f"Offset: {float(time.clock_gettime(time.CLOCK_BOOTTIME)) - float(time_since_start())}")


class InvalidServiceError(Exception):
    pass

class ServiceInfo(TypedDict):
    name: str
    status: int | None
    pid: int
    oneshot_game: bool
    crashed: bool

def eshell():
    try:
        print(f"[{time_since_start()}]{Colour.RED} Starting emergency shell...{Colour.RESET}")
        while True:
            subprocess.run(["/bin/login"])
    except FileNotFoundError as e:
        print(f"[{time_since_start()}] Emergency shell failed: {e}")
        print("WHAT THE FUCK! Ok, you are not on a real machine, fuck you, hey kernel, crash.")
        print(f"{Colour.YELLOW}Kernel:{Colour.RED} Ok{Colour.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"[{time_since_start()}] Emergency shell failed: {e}")
        print(f"Stupid unhandled exception, hey, now it's handled... I wonder...{Colour.GREEN} Can I make the kernel crash green?")
        sys.exit(1)

def reap():
    # As PID 1 we inherit every orphan on the system, so collect everything
    # that has exited. Services get their exit code recorded; anything else
    # is an orphan nobody else was going to clean up.
    while True:
        try:
            pid, raw_status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return  # no children left at all
        if pid == 0:
            return  # children exist, none have exited yet
        name = pid_to_service.pop(pid, None)
        if name is not None:
            exit_status[name] = os.waitstatus_to_exitcode(raw_status)
        else:
            log(f"[{time_since_start()}] Reaped orphan {pid}, it's ours now, I guess")

def get_service(service_name: str, allow_graceful_exit: bool = False) -> ServiceInfo:
    pid = service_list[service_name][0].pid
    status = exit_status.get(service_name)
    if allow_graceful_exit and status == 0:
        crashed = False
    elif status is None:
        crashed = False
    else:
        crashed = True

    return {"name": service_name, "status": status, "pid": pid, "oneshot_game": allow_graceful_exit, "crashed": crashed}
    

def start_service(service_name: str, command: list[str], oneshot_game: bool = False):
    global service_list, failed_list
    if not service_name or not command:
        raise InvalidServiceError("Incorrect usage :(")
    if (service_name in service_list) and not service_name in failed_list:
        raise InvalidServiceError("Service already running correctly owo")

    
    if service_name in failed_list and failed_list[service_name] > 3:
        msg = f"[{time_since_start()}] Service {service_name} repeatedly crashed, refusing to start..."
        if not booted:
            print(msg)
        else:
            log(msg)
        return
    process = subprocess.Popen(command)
    service_list[service_name] = [process, oneshot_game, command]
    pid_to_service[process.pid] = service_name
    exit_status[service_name] = None
    time.sleep(0.5)
    reap()
    status = get_service(service_name, allow_graceful_exit=oneshot_game)
    if status["crashed"]:
        # failed_list maps service name -> number of failed starts
        failed_list[service_name] = failed_list.get(service_name, 0) + 1
        msg = f"[{time_since_start()}] {Colour.RED}Failed to start {service_name}"
        if not booted:
            print(msg)
        else:
            log(msg)
    else:
        msg = f"[{time_since_start()}] {Colour.GREEN}Started {service_name}{Colour.RESET}"
        if not booted:
            print(msg)
        else:
            log(msg)
    
def stop_service(service):
    global service_list
    pid = service_list[service][0].pid
    if exit_status.get(service) is None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        timer = 20
        while timer and exit_status.get(service) is None:
            reap()
            timer -= 1
            time.sleep(1)
    if exit_status.get(service) is None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        while exit_status.get(service) is None:
            reap()
            time.sleep(0.1)
    service_list.pop(service)
    exit_status.pop(service, None)

def restart_service(service):
    _, oneshot, command = service_list[service]
    stop_service(service)
    start_service(service_name=service, command=command, oneshot_game=oneshot)
    
        

def mount(command):
    mount_point = command[-1]
    print(f"[{time_since_start()}] Mounting: {mount_point}")

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

def stopping_all():
    for i in dict(service_list):
        print(f"[{time_since_start()}] Stopping {i}")
        stop_service(i)

def handle_command(command: list):
    try:
        _ = command[0]
    except:
        return
    if command[0] == "shutdown":
        print("The system will now shut down.")
        print(f"[{time_since_start()}] {Colour.RED}Preparing to shutdown{Colour.RESET}")
        stopping_all()
        print(f"[{time_since_start()}] All services have been shut down")
        print(f"[{time_since_start()}] {Colour.CYAN}libc.sync(){Colour.RESET}")
        libc.sync()
        print("I have enjoyed running, goodnight.")
        print(f"[{time_since_start()}] Kernel time: {float(time.clock_gettime(time.CLOCK_BOOTTIME))}")
        libc.syscall(169, _MAGIC1, _MAGIC2, _CMD_POWER_OFF, 0)
    elif command[0] == "reboot":
        print("The system will now come back another time.")
        print(f"[{time_since_start()}] {Colour.RED}Preparing to reboot{Colour.RESET}")
        stopping_all()
        print(f"[{time_since_start()}] All services have been shut down")
        print(f"[{time_since_start()}] {Colour.CYAN}libc.sync(){Colour.RESET}")
        libc.sync()
        print('Fuck death, I will jump in front of a van and survive owo')
        print(f"[{time_since_start()}] Kernel time: {float(time.clock_gettime(time.CLOCK_BOOTTIME))}")
        libc.syscall(169, _MAGIC1, _MAGIC2, _CMD_RESTART, 0)


class HostNameError(Exception):
    pass 



def boot():
    print(f"[{time_since_start()}] Starting services...")
    # Load services from /etc/pintinit/config.py
    config_path = "/etc/pintinit/config.py"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
    except Exception as e:
        traceback.print_exc()
        print(f"[{time_since_start()}] Failed to load configuration from {config_path}")
        eshell()
    print(f"[{time_since_start()}] {Colour.CYAN}Setting hostname{Colour.RESET}")
    hostsrc = "None"
    try:
        hostname = config.hostname
        hostsrc = "config.py"
        if (hostname is None) or (hostname == ""):
            raise HostNameError
    except (HostNameError, AttributeError):
        try:
            with open("/etc/hostname", encoding="utf-8") as f:
                hostname = f.readline().strip() or "localhost"
                hostsrc = "/etc/hostname"
        except FileNotFoundError:
            hostname = "localhost"
            hostsrc = "Compiled backup"
    libc.sethostname.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    libc.sethostname.restype = ctypes.c_int
    encoded = hostname.encode("utf-8")
    if libc.sethostname(encoded, len(encoded)) != 0:
        error = ctypes.get_errno()
        print(f"[{time_since_start()}] {Colour.YELLOW}{error}: Failed to set hostname, continuing to eat you...{Colour.RESET}")
    else:
        print(f"[{time_since_start()}] {Colour.GREEN}Set hostname to: {hostname}{Colour.RESET}")
        print(f"[{time_since_start()}] Hostname source: {hostsrc}")
    for i in config.services:
        print(f"[{time_since_start()}] {Colour.CYAN}Starting service {i[0]}...{Colour.RESET}")
        try:
            start_service(i[0], i[2], i[3])
        except Exception as e:
            traceback.print_exc()
            print(f"[{time_since_start()}] Failed to start service {i[0]}: {e}")
            eshell()
            


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

boot()
server = setup_command_socket()
booted = True

while True:
    reap()
    service_list_temp = dict(service_list)
    for i in service_list_temp:
        service_poll = get_service(i, allow_graceful_exit=service_list_temp[i][1])
        if service_poll["crashed"]:
            restart_service(service_poll["name"])
    for command in get_commands(server):
        handle_command(command)
    time.sleep(0.01)

