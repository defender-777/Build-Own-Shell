import sys
import os
import subprocess
import shlex

# Builtin commands
BUILTINS = {"exit", "echo", "type", "pwd", "cd"}


def find_executable(command: str):
    """
    Search for an executable:
    - If command contains '/', treat it as a path.
    - Else search current directory.
    - Then search PATH.
    """
    # Case 1: explicit path
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    # Case 2: current working directory
    cwd_path = os.path.join(os.getcwd(), command)
    if os.path.isfile(cwd_path) and os.access(cwd_path, os.X_OK):
        return cwd_path

    # Case 3: PATH search
    path_env = os.environ.get("PATH", "")
    for directory in path_env.split(":"):
        if not directory:
            continue
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


def parse_redirections(tokens):
    """
    Parse redirection operators from token list.

    Supported:
      >, 1>      : stdout overwrite
      >>, 1>>    : stdout append
      2>         : stderr overwrite
      2>>        : stderr append

    Returns:
      cmd_tokens, stdout_redir, stdout_append, stderr_redir, stderr_append, error_msg
    """
    stdout_redir = None
    stdout_append = False
    stderr_redir = None
    stderr_append = False

    cmd_tokens = []
    i = 0
    n = len(tokens)

    while i < n:
        t = tokens[i]

        # stdout overwrite
        if t in (">", "1>"):
            if i + 1 >= n:
                return None, None, False, None, False, "syntax error: expected filename after >"
            stdout_redir = tokens[i + 1]
            stdout_append = False
            i += 2
            continue

        # stdout append
        if t in (">>", "1>>"):
            if i + 1 >= n:
                return None, None, False, None, False, "syntax error: expected filename after >>"
            stdout_redir = tokens[i + 1]
            stdout_append = True
            i += 2
            continue

        # stderr overwrite
        if t == "2>":
            if i + 1 >= n:
                return None, None, False, None, False, "syntax error: expected filename after 2>"
            stderr_redir = tokens[i + 1]
            stderr_append = False
            i += 2
            continue

        # stderr append
        if t == "2>>":
            if i + 1 >= n:
                return None, None, False, None, False, "syntax error: expected filename after 2>>"
            stderr_redir = tokens[i + 1]
            stderr_append = True
            i += 2
            continue

        # normal command/arg token
        cmd_tokens.append(t)
        i += 1

    if not cmd_tokens:
        return None, stdout_redir, stdout_append, stderr_redir, stderr_append, "syntax error: missing command"

    return cmd_tokens, stdout_redir, stdout_append, stderr_redir, stderr_append, None


def run_external(cmd_tokens, stdout_redir, stdout_append, stderr_redir, stderr_append):
    """
    Run an external command with optional stdout/stderr redirections.
    """
    executable_path = find_executable(cmd_tokens[0])
    if not executable_path:
        print(f"{cmd_tokens[0]}: command not found")
        return

    # Build argv ensuring argv[0] is the command, not the full path
    argv = [cmd_tokens[0]] + cmd_tokens[1:]

    stdout_target = sys.stdout
    stderr_target = sys.stderr
    stdout_file = None
    stderr_file = None

    try:
        if stdout_redir is not None:
            mode = "a" if stdout_append else "w"
            stdout_file = open(stdout_redir, mode)
            stdout_target = stdout_file

        if stderr_redir is not None:
            mode = "a" if stderr_append else "w"
            stderr_file = open(stderr_redir, mode)
            stderr_target = stderr_file

        subprocess.run(
            argv,
            executable=executable_path,
            stdout=stdout_target,
            stderr=stderr_target,
        )
    except Exception as e:
        print(f"Error executing {cmd_tokens[0]}: {e}")
    finally:
        if stdout_file is not None:
            stdout_file.close()
        if stderr_file is not None:
            stderr_file.close()


def run_pipeline(left_tokens, right_tokens):
    """
    Run a simple pipeline: left | right
    Only external commands are expected here (per Codecrafters stage spec).
    """
    if not left_tokens or not right_tokens:
        print("syntax error: invalid pipeline")
        return

    left_exec = find_executable(left_tokens[0])
    right_exec = find_executable(right_tokens[0])

    if not left_exec:
        print(f"{left_tokens[0]}: command not found")
        return
    if not right_exec:
        print(f"{right_tokens[0]}: command not found")
        return

    left_argv = [left_tokens[0]] + left_tokens[1:]
    right_argv = [right_tokens[0]] + right_tokens[1:]

    # left stdout -> pipe -> right stdin
    p1 = subprocess.Popen(
        left_argv,
        executable=left_exec,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )

    p2 = subprocess.Popen(
        right_argv,
        executable=right_exec,
        stdin=p1.stdout,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Allow p1 to receive SIGPIPE when p2 exits
    p1.stdout.close()
    # Wait for right side to complete (e.g., head -n 5)
    p2.communicate()
    # Optionally wait for left
    p1.wait()


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

        # Tokenize with shlex to handle quotes properly
        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"Syntax error: {e}")
            continue

        if not tokens:
            continue

        # --- Pipelines: command1 | command2 (two external commands) ---
        if "|" in tokens:
            pipe_index = tokens.index("|")
            left_tokens = tokens[:pipe_index]
            right_tokens = tokens[pipe_index + 1:]
            run_pipeline(left_tokens, right_tokens)
            continue

        # --- Redirections (>, >>, 2>, 2>>) ---
        (
            cmd_tokens,
            stdout_redir,
            stdout_append,
            stderr_redir,
            stderr_append,
            err,
        ) = parse_redirections(tokens)

        if err is not None:
            print(err)
            continue

        command = cmd_tokens[0]
        args = cmd_tokens[1:]

        # If *any* redirection is present, we always run via external executable,
        # not via builtins (this matches Codecrafters test expectations).
        if stdout_redir is not None or stderr_redir is not None:
            run_external(cmd_tokens, stdout_redir, stdout_append, stderr_redir, stderr_append)
            continue

        # ========================
        #       BUILTINS
        # ========================

        # exit builtin
        if command == "exit":
            exit_code = 0
            if args:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # echo builtin
        elif command == "echo":
            print(" ".join(args))

        # pwd builtin
        elif command == "pwd":
            print(os.getcwd())

        # cd builtin (absolute, relative, ~, and no-arg -> home)
        elif command == "cd":
            if not args:
                path = os.path.expanduser("~")
            else:
                path = os.path.expanduser(args[0])

            # Resolve relative to current directory
            if not path.startswith("/"):
                path = os.path.abspath(os.path.join(os.getcwd(), path))

            try:
                os.chdir(path)
            except FileNotFoundError:
                if args:
                    print(f"cd: {args[0]}: No such file or directory")
                else:
                    print(f"cd: {path}: No such file or directory")

        # type builtin
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

        # ========================
        #   EXTERNAL COMMANDS
        # ========================
        else:
            executable_path = find_executable(command)
            if executable_path:
                try:
                    subprocess.run(
                        [command] + args,
                        executable=executable_path,
                        stdout=sys.stdout,
                        stderr=sys.stderr,
                    )
                except Exception as e:
                    print(f"Error executing {command}: {e}")
            else:
                print(f"{command}: command not found")


if __name__ == "__main__":
    main()
