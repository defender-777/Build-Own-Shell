import sys
import os
import subprocess

# Builtin commands
BUILTINS = {"exit", "echo", "type", "pwd", "cd"}

def find_executable(command):
    """Search PATH for an executable file and return its full path if found."""
    for directory in os.environ["PATH"].split(":"):
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None

def main():
    while True:
        try:
            # Display prompt
            sys.stdout.write("$ ")
            sys.stdout.flush()
            line = input()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        command = tokens[0]
        args = tokens[1:]

        # --- exit builtin ---
        if command == "exit":
            exit_code = 0
            if args:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # --- echo builtin ---
        elif command == "echo":
            print(" ".join(args))

        # --- pwd builtin ---
        elif command == "pwd":
            print(os.getcwd())

        # --- cd builtin (absolute + relative paths) ---
        elif command == "cd":
            if not args:
                print("cd: missing argument")
                continue

            target_path = args[0]

            # Convert to absolute path if relative
            if not os.path.isabs(target_path):
                target_path = os.path.abspath(os.path.join(os.getcwd(), target_path))

            # Try to change directory
            try:
                os.chdir(target_path)
            except FileNotFoundError:
                print(f"cd: {args[0]}: No such file or directory")
            except NotADirectoryError:
                print(f"cd: {args[0]}: Not a directory")

        # --- type builtin ---
        elif command == "type":
            if not args:
                print("type: missing argument")
                continue

            target = args[0]
            if target in BUILTINS:
                print(f"{target} is a shell builtin")
                continue

            executable_path = find_executable(target)
            if executable_path:
                print(f"{target} is {executable_path}")
            else:
                print(f"{target}: not found")

        # --- External programs ---
        else:
            executable_path = find_executable(command)
            if executable_path:
                try:
                    subprocess.run([command] + args, executable=executable_path)
                except Exception as e:
                    print(f"Error executing {command}: {e}")
            else:
                print(f"{command}: command not found")

if __name__ == "__main__":
    main()
