import os
import sys
import shlex
import subprocess

# ----------------------------------------------------------------------
# GLOBAL HISTORY LIST
# ----------------------------------------------------------------------
HISTORY = []

# ----------------------------------------------------------------------
# BUILTINS
# ----------------------------------------------------------------------
BUILTINS = {"exit", "echo", "type", "pwd", "cd", "history"}


# ----------------------------------------------------------------------
# EXECUTABLE LOOKUP
# ----------------------------------------------------------------------
def find_executable(command: str):
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    # Check CWD
    cwd_path = os.path.join(os.getcwd(), command)
    if os.path.isfile(cwd_path) and os.access(cwd_path, os.X_OK):
        return cwd_path

    # Check PATH
    for directory in os.environ.get("PATH", "").split(":"):
        if not directory:
            continue
        path = os.path.join(directory, command)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


# ----------------------------------------------------------------------
# REDIRECTION PARSER
# ----------------------------------------------------------------------
def parse_redirections(tokens):
    argv = []
    stdout_path = None
    stdout_append = False
    stderr_path = None
    stderr_append = False

    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t in (">", "1>"):
            stdout_path = tokens[i + 1]
            stdout_append = False
            i += 2
            continue

        if t in (">>", "1>>"):
            stdout_path = tokens[i + 1]
            stdout_append = True
            i += 2
            continue

        if t == "2>":
            stderr_path = tokens[i + 1]
            stderr_append = False
            i += 2
            continue

        if t == "2>>":
            stderr_path = tokens[i + 1]
            stderr_append = True
            i += 2
            continue

        argv.append(t)
        i += 1

    return argv, stdout_path, stdout_append, stderr_path, stderr_append


# ----------------------------------------------------------------------
# BUILTIN RUNNER
# ----------------------------------------------------------------------
def run_builtin(command, args, stdout_stream, stderr_stream):
    if command == "exit":
        code = int(args[0]) if args else 0
        sys.exit(code)

    elif command == "echo":
        print(" ".join(args), file=stdout_stream)

    elif command == "pwd":
        print(os.getcwd(), file=stdout_stream)

    elif command == "cd":
        target = args[0] if args else os.path.expanduser("~")
        target = os.path.expanduser(target)
        if not target.startswith("/"):
            target = os.path.abspath(os.path.join(os.getcwd(), target))
        try:
            os.chdir(target)
        except FileNotFoundError:
            print(f"cd: {args[0]}: No such file or directory", file=stderr_stream)

    elif command == "type":
        if not args:
            print("type: missing argument", file=stderr_stream)
            return
        name = args[0]
        if name in BUILTINS:
            print(f"{name} is a shell builtin", file=stdout_stream)
            return
        exe = find_executable(name)
        if exe:
            print(f"{name} is {exe}", file=stdout_stream)
        else:
            print(f"{name}: not found", file=stdout_stream)

    elif command == "history":
        # history <n>
        if args:
            try:
                n = int(args[0])
            except ValueError:
                print(f"history: {args[0]}: numeric argument required", file=stderr_stream)
                return

            # Slice last n commands
            start_idx = max(0, len(HISTORY) - n)
            for idx in range(start_idx, len(HISTORY)):
                print(f"{idx + 1:5d}  {HISTORY[idx]}", file=stdout_stream)
            return

        # history → full list
        for idx, entry in enumerate(HISTORY, start=1):
            print(f"{idx:5d}  {entry}", file=stdout_stream)


# ----------------------------------------------------------------------
# RUN SINGLE COMMAND
# ----------------------------------------------------------------------
def run_single(tokens):
    argv, out, out_app, err, err_app = parse_redirections(tokens)
    if not argv:
        return

    cmd = argv[0]
    args = argv[1:]

    stdout_stream = sys.stdout
    stderr_stream = sys.stderr
    out_f = None
    err_f = None

    try:
        if out:
            out_f = open(out, "a" if out_app else "w")
            stdout_stream = out_f

        if err:
            err_f = open(err, "a" if err_app else "w")
            stderr_stream = err_f

        if cmd in BUILTINS:
            run_builtin(cmd, args, stdout_stream, stderr_stream)
            return

        exe = find_executable(cmd)
        if not exe:
            print(f"{cmd}: command not found", file=stdout_stream)
            return

        subprocess.run([cmd] + args, executable=exe,
                       stdout=stdout_stream, stderr=stderr_stream)

    finally:
        if out_f: out_f.close()
        if err_f: err_f.close()


# ----------------------------------------------------------------------
# PIPELINE SPLIT
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
# MULTI-STAGE PIPELINE EXECUTION
# ----------------------------------------------------------------------
def run_pipeline(tokens):
    stages = split_pipeline(tokens)

    # Special case: last stage is builtin "type"
    if stages[-1] and stages[-1][0] == "type":
        argv, _, _, _, _ = parse_redirections(stages[-1])
        if argv:
            run_builtin("type", argv[1:], sys.stdout, sys.stderr)
        return

    processes = []
    prev = None

    for i, stage in enumerate(stages):
        if not stage:
            continue

        cmd = stage[0]
        args = stage[1:]
        exe = find_executable(cmd)

        if not exe:
            print(f"{cmd}: command not found")
            return

        stdin = prev.stdout if prev else None
        stdout = None if i == len(stages) - 1 else subprocess.PIPE

        p = subprocess.Popen(
            [cmd] + args,
            executable=exe,
            stdin=stdin,
            stdout=stdout,
            stderr=sys.stderr
        )

        if prev and prev.stdout:
            prev.stdout.close()

        prev = p
        processes.append(p)

    for p in processes:
        p.wait()


# ----------------------------------------------------------------------
# MAIN SHELL LOOP
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

        # Store full raw command into history
        HISTORY.append(line)

        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"Syntax error: {e}")
            continue

        if "|" in tokens:
            run_pipeline(tokens)
        else:
            run_single(tokens)


if __name__ == "__main__":
    main()
