"""
services
* denotes required

str: name: The name of a service or unit*
str: desc: The description of a service or unit
list: command: The command to run to start the service or unit, note, index 0 is always the command, so if index 0 is /bin/bash login, the system will try to find binary "bash login" in /bin/, and will result in a failure
bool: oneshot-game: If the unit should not be restarted if exits with error code 0 (gracefull exit)
list: req: Do not start unit if other units have not started

example:
services = [
    # ["name", "desc", ["command", "here"], oneshot-game, ["requires", "unit"]]
    ["basic-login-test@tty1", "Launch a basic shell", ["/sbin/agetty", "-o", "-p -- \\u", "--noclear", "tty1", "linux"], False, []],
    ["basic-login-test@ttyS0", "Launch a serial console login", ["/sbin/agetty", "-o", "-p -- \\u", "--noclear", "115200", "ttyS0", "vt100"], False, []]
]
"""

services = [
    # ["name", "desc", ["command", "here"], oneshot-game, ["requires", "unit"]]
    ["basic-login-test@tty1", "Launch a basic shell", ["/sbin/agetty", "-o", "-p -- \\u", "--noclear", "tty1", "linux"], False, []],
    ["basic-login-test@ttyS0", "Launch a serial console login", ["/sbin/agetty", "-o", "-p -- \\u", "--noclear", "115200", "ttyS0", "vt100"], False, []]
]

"""
hostname

Name the system anything
This is mainly cosmetic last time I checked.
This is often seen at the start of a shell, like user@localhost, where localhost is the hostname

example:
hostname = "nyaa"
# root@nyaa ~ >

"""
hostname = "pintinit-nyaa"