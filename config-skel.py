"""
* denotes required

str: name: The name of a service or unit*
str: desc: The description of a service or unit
list: command: The command to run to start the service or unit, note, index 0 is always the command, so if index 0 is /bin/bash login, the system will try to find binary "bash login" in /bin/, and will result in a failure
bool: oneshot-game: If the unit should not be restarted if exits with error code 0 (gracefull exit)
list: req: Do not start unit if other units have not started
"""

services = [
    # ["name", "desc", ["command", "here"], oneshot-game, ["requres", "unit"]]
    ["basic-login-test", "Launch a basic shell", ["/sbin/agetty", "-o", "-p -- \\u", "--noclear", "tty1", "linux"], False, []]
]