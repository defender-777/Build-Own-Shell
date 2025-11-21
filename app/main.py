import sys
import os
import subprocess
import shlex

BUILTINS = {"exit", "echo", "type", "pwd", "cd"}

def find_executable(command):
    """Search PATH and current directory for an executable."""
    # Case 1: If command includes a path
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    # Case 2: Current directory
    cwd_path = os.path.join(os.getcwd(), command)
    if os.path.isfile(cwd_path) and os.access(cwd_path, os.X_OK):
        return cwd_path

    # Case 3: PATH directories
    for directory in os.environ["PATH"].split(":"):
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


def main():
    while True:
        try:
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

        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"Syntax error: {e}")
            continue

        if not tokens:
            continue

        # --- Handle append redirection (1>> or >>) ---
        if ">>" in tokens or "1>>" in tokens:
            if ">>" in tokens:
                redir_index = tokens.index(">>")
            else:
                redir_index = tokens.index("1>>")

            cmd_tokens = tokens[:redir_index]
            if redir_index + 1 >= len(tokens):
                print("syntax error: expected filename after >>")
                continue
            outfile = tokens[redir_index + 1]

            if not cmd_tokens:
                print("syntax error: missing command before >>")
                continue

            executable_path = find_executable(cmd_tokens[0])
            if not executable_path:
                print(f"{cmd_tokens[0]}: command not found")
                continue

            try:
                # "a" = append mode
                with open(outfile, "a") as f:
                    subprocess.run(
                        [cmd_tokens[0]] + cmd_tokens[1:],
                        executable=executable_path,
                        stdout=f,
                        stderr=sys.stderr
                    )
            except Exception as e:
                print(f"Error executing {cmd_tokens[0]}: {e}")

            continue

        # --- Handle stdout redirection (1> or >) ---
        if ">" in tokens or "1>" in tokens:
            if ">" in tokens:
                redir_index = tokens.index(">")
            else:
                redir_index = tokens.index("1>")

            cmd_tokens = tokens[:redir_index]
            if redir_index + 1 >= len(tokens):
                print("syntax error: expected filename after >")
                continue
            outfile = tokens[redir_index + 1]

            if not cmd_tokens:
                print("syntax error: missing command before >")
                continue

            executable_path = find_executable(cmd_tokens[0])
            if not executable_path:
                print(f"{cmd_tokens[0]}: command not found")
                continue

            try:
                # "w" = overwrite mode
                with open(outfile, "w") as f:
                    subprocess.run(
                        [cmd_tokens[0]] + cmd_tokens[1:],
                        executable=executable_path,
                        stdout=f,
                        stderr=sys.stderr
                    )
            except Exception as e:
                print(f"Error executing {cmd_tokens[0]}: {e}")

            continue

        # --- Handle stderr redirection (2>) ---
        if "2>" in tokens:
            redir_index = tokens.index("2>")

            cmd_tokens = tokens[:redir_index]
            if redir_index + 1 >= len(tokens):
                print("syntax error: expected filename after 2>")
                continue
            errfile = tokens[redir_index + 1]

            executable_path = find_executable(cmd_tokens[0])
            if not executable_path:
                print(f"{cmd_tokens[0]}: command not found")
                continue

            try:
                with open(errfile, "w") as f:
                    subprocess.run(
                        [cmd_tokens[0]] + cmd_tokens[1:],
                        executable=executable_path,
                        stdout=sys.stdout,
                        stderr=f
                    )
            except Exception as e:
                print(f"Error executing {cmd_tokens[0]}: {e}")

            continue

        # --- Normal command handling ---
        command = tokens[0]
        args = tokens[1:]

        # Builtin: exit
        if command == "exit":
            exit_code = 0
            if args:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # Builtin: echo
        elif command == "echo":
            print(" ".join(args))

        # Builtin: pwd
        elif command == "pwd":
            print(os.getcwd())

        # Builtin: cd
        elif command == "cd":
            if not args:
                path = os.path.expanduser("~")
            else:
                path = os.path.expanduser(args[0])
            if not path.startswith("/"):
                path = os.path.abspath(os.path.join(os.getcwd(), path))
            try:
                os.chdir(path)
            except FileNotFoundError:
                print(f"cd: {args[0]}: No such file or directory" if args else f"cd: {path}: No such file or directory")

        # Builtin: type
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

        # External Commands
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