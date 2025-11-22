import os
import sys
import shlex
import subprocess

# ----------------------------------------------------------------------
# Builtin commands, now includes "history"
# ----------------------------------------------------------------------

BUILTINS = {"exit", "echo", "type", "pwd", "cd", "history"}


# ----------------------------------------------------------------------
# Utility: find an executable (PATH search + cwd)
# ----------------------------------------------------------------------

def find_executable(command: str):
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    cwd_path = os.path.join(os.getcwd(), command)
    if os.path.isfile(cwd_path) and os.access(cwd_path, os.X_OK):
        return cwd_path

    path_env = os.environ.get("PATH", "")
    for directory in path_env.split(":"):
        if not directory:
            continue
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


# ----------------------------------------------------------------------
# Parse redirections for a *single* command (no pipes)
# ----------------------------------------------------------------------

def parse_redirections(tokens):
    argv = []
    stdout_path = None
    stdout_append = False
    stderr_path = None
    stderr_append = False

    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]

        if t in (">", "1>"):
            if i + 1 >= n:
                print("syntax error: expected filename after '>'")
                return None, None, None, None, None
            stdout_path = tokens[i + 1]
            stdout_append = False
            i += 2
            continue

        if t in (">>", "1>>"):
            if i + 1 >= n:
                print("syntax error: expected filename after '>>'")
                return None, None, None, None, None
            stdout_path = tokens[i + 1]
            stdout_append = True
            i += 2
            continue

        if t == "2>":
            if i + 1 >= n:
                print("syntax error: expected filename after '2>'")
                return None, None, None, None, None
            stderr_path = tokens[i + 1]
            stderr_append = False
            i += 2
            continue

        if t == "2>>":
            if i + 1 >= n:
                print("syntax error: expected filename after '2>>'")
                return None, None, None, None, None
            stderr_path = tokens[i + 1]
            stderr_append = True
            i += 2
            continue

        argv.append(t)
        i += 1

    return argv, stdout_path, stdout_append, stderr_path, stderr_append


# ----------------------------------------------------------------------
# Builtin execution
# ----------------------------------------------------------------------

def run_builtin(command, args, stdout_stream, stderr_stream):
    if command == "exit":
        exit_code = 0
        if args:
            try:
                exit_code = int(args[0])
            except ValueError:
                print(f"exit: {args[0]}: numeric argument required", file=stderr_stream)
                exit_code = 1
        sys.exit(exit_code)

    elif command == "echo":
        print(" ".join(args), file=stdout_stream)

    elif command == "pwd":
        print(os.getcwd(), file=stdout_stream)

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
            if args:
                print(f"cd: {args[0]}: No such file or directory", file=stderr_stream)
            else:
                print(f"cd: {path}: No such file or directory", file=stderr_stream)

    elif command == "type":
        if not args:
            print("type: missing argument", file=stderr_stream)
            return
        target = args[0]

        if target in BUILTINS:
            print(f"{target} is a shell builtin", file=stdout_stream)
            return

        exe = find_executable(target)
        if exe:
            print(f"{target} is {exe}", file=stdout_stream)
        else:
            print(f"{target}: not found", file=stdout_stream)

    elif command == "history":
        # Only recognition needed for this Codecrafters stage
        # Full history implementation comes later
        pass


# ----------------------------------------------------------------------
# Run a *single* command (no pipeline)
# ----------------------------------------------------------------------

def run_single_command(tokens):
    argv, stdout_path, stdout_append, stderr_path, stderr_append = parse_redirections(tokens)
    if argv is None:
        return

    if not argv:
        return

    command = argv[0]
    args = argv[1:]

    stdout_stream = sys.stdout
    stderr_stream = sys.stderr
    stdout_file = None
    stderr_file = None

    try:
        if stdout_path is not None:
            mode = "a" if stdout_append else "w"
            stdout_file = open(stdout_path, mode)
            stdout_stream = stdout_file

        if stderr_path is not None:
            mode = "a" if stderr_append else "w"
            stderr_file = open(stderr_path, mode)
            stderr_stream = stderr_file

        if command in BUILTINS:
            run_builtin(command, args, stdout_stream, stderr_stream)
            return

        exe = find_executable(command)
        if not exe:
            print(f"{command}: command not found", file=stdout_stream)
            return

        subprocess.run(
            [command] + args,
            executable=exe,
            stdout=stdout_stream,
            stderr=stderr_stream
        )

    finally:
        if stdout_file is not None:
            stdout_file.close()
        if stderr_file is not None:
            stderr_file.close()


# ----------------------------------------------------------------------
# Split pipeline tokens (cmd1 | cmd2 | cmd3 ...)
# ----------------------------------------------------------------------

def split_pipeline(tokens):
    stages = [[]]
    for t in tokens:
        if t == "|":
            stages.append([])
        else:
            stages[-1].append(t)
    return [s for s in stages if s]


# ----------------------------------------------------------------------
# Full Multi-Stage Pipeline Execution (external commands only)
# ----------------------------------------------------------------------

def run_pipeline(tokens):
    stages = split_pipeline(tokens)
    if not stages:
        return

    # Special case: if last is builtin 'type'
    last = stages[-1]
    if last and last[0] == "type":
        argv, _, _, _, _ = parse_redirections(last)
        if argv:
            cmd = argv[0]
            args = argv[1:]
            if cmd == "type":
                run_builtin("type", args, sys.stdout, sys.stderr)
        return

    processes = []
    prev_proc = None

    for i, stage_tokens in enumerate(stages):
        if not stage_tokens:
            continue

        cmd = stage_tokens[0]
        args = stage_tokens[1:]

        exe = find_executable(cmd)
        if not exe:
            print(f"{cmd}: command not found")
            return

        if prev_proc is None:
            stdin_pipe = None
        else:
            stdin_pipe = prev_proc.stdout

        if i == len(stages) - 1:
            stdout_pipe = None
        else:
            stdout_pipe = subprocess.PIPE

        p = subprocess.Popen(
            [cmd] + args,
            executable=exe,
            stdin=stdin_pipe,
            stdout=stdout_pipe,
            stderr=sys.stderr
        )

        if prev_proc is not None and prev_proc.stdout is not None:
            prev_proc.stdout.close()

        prev_proc = p
        processes.append(p)

    for p in processes:
        p.wait()


# ----------------------------------------------------------------------
# Main shell REPL
# ----------------------------------------------------------------------

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

        if "|" in tokens:
            run_pipeline(tokens)
        else:
            run_single_command(tokens)


if __name__ == "__main__":
    main()
