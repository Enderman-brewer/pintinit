#!/usr/bin/env python3
import socket
import json
import sys

def main():
    # Corrected path for pintinit
    SOCKET_PATH = '/run/pintinit.sock'

    # Ensure the user provided at least one argument
    if len(sys.argv) < 2:
        print("Usage: mainctl <command> [args...]")
        print("Example: mainctl start nginx")
        sys.exit(1)

    # Capture all arguments passed to the script (excluding the script name itself)
    command_payload = sys.argv[1:]

    try:
        # Connect to the Unix domain socket
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client_socket:
            client_socket.connect(SOCKET_PATH)
            
            # Serialize the arguments to JSON and encode to bytes
            json_data = json.dumps(command_payload).encode('utf-8')
            
            # Send the complete payload to pintinit
            client_socket.sendall(json_data)
            
    except FileNotFoundError:
        print(f"Error: The socket file '{SOCKET_PATH}' does not exist. Is pintinit running?")
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied. Try running with 'sudo'.")
        sys.exit(1)
    except ConnectionRefusedError:
        print(f"Error: Connection refused. The socket exists, but pintinit isn't listening.")
        sys.exit(1)

if __name__ == '__main__':
    main()
