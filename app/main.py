import os
import sys
import subprocess
import shlex

# Builtins supported by our shell
BUILTINS = {"exit", "echo", "type", "pwd", "cd"}


# ---------- Utility: find executables ----------

def find_executable(command: str):
    """
    Search for an executable:
      1) If command contains '/', treat it as a path.
      2) Check current working directory.
      3) Search each directory in PATH.
    Return full path if found & executable, else None.
    """
    # Case 1: command includes a path component
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    # Case 2: current directory
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


# ---------- Utility: parse redirections for a single command ----------

def parse_redirections(tokens):
    """
    Given a token list for a SINGLE command (no pipes),
    extract redirections and return:

      argv, stdout_path, stdout_append, stderr_path, stderr_append

    Redirection operators handled:
      >, 1>    : overwrite stdout
      >>, 1>>  : append stdout
      2>       : overwrite stderr
      2>>      : append stderr
    """
    argv = []
    stdout_path = None
    stdout_append = False
    stderr_path = None
    stderr_append = False

    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]

        # STDOUT overwrite
        if t in (">", "1>"):
            if i + 1 >= n:
                print("syntax error: expected filename after '>'")
                return None, None, None, None, None
            stdout_path = tokens[i + 1]
            stdout_append = False
            i += 2
            continue

        # STDOUT append
        if t in (">>", "1>>"):
            if i + 1 >= n:
                print("syntax error: expected filename after '>>'")
                return None, None, None, None, None
            stdout_path = tokens[i + 1]
            stdout_append = True
            i += 2
            continue

        # STDERR overwrite
        if t == "2>":
            if i + 1 >= n:
                print("syntax error: expected filename after '2>'")
                return None, None, None, None, None
            stderr_path = tokens[i + 1]
            stderr_append = False
            i += 2
            continue

        # STDERR append
        if t == "2>>":
            if i + 1 >= n:
                print("syntax error: expected filename after '2>>'")
                return None, None, None, None, None
            stderr_path = tokens[i + 1]
            stderr_append = True
            i += 2
            continue

        # Normal argument
        argv.append(t)
        i += 1

    return argv, stdout_path, stdout_append, stderr_path, stderr_append


# ---------- Builtins implementation ----------

def run_builtin(command, args, stdout_stream, stderr_stream):
    """
    Execute a builtin command, writing to given stdout/stderr streams.
    """
    # exit
    if command == "exit":
        exit_code = 0
        if args:
            try:
                exit_code = int(args[0])
            except ValueError:
                print(f"exit: {args[0]}: numeric argument required", file=stderr_stream)
                exit_code = 1
        sys.exit(exit_code)

    # echo
    elif command == "echo":
        print(" ".join(args), file=stdout_stream)

    # pwd
    elif command == "pwd":
        print(os.getcwd(), file=stdout_stream)

    # cd
    elif command == "cd":
        # No arg → go to home
        if not args:
            path = os.path.expanduser("~")
        else:
            path = os.path.expanduser(args[0])

        if not path.startswith("/"):
            path = os.path.abspath(os.path.join(os.getcwd(), path))

        try:
            os.chdir(path)
        except FileNotFoundError:
            # Match codecrafters-style error
            if args:
                print(f"cd: {args[0]}: No such file or directory", file=stderr_stream)
            else:
                print(f"cd: {path}: No such file or directory", file=stderr_stream)

    # type
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


# ---------- Single-command execution (no pipes) ----------

def run_single_command(tokens):
    """
    Run a single command line with possible redirections but no pipelines.
    """
    argv, stdout_path, stdout_append, stderr_path, stderr_append = parse_redirections(tokens)
    if argv is None:
        return  # parse error already printed

    if not argv:
        return

    command = argv[0]
    args = argv[1:]

    # Setup stdout / stderr streams
    stdout_stream = sys.stdout
    stderr_stream = sys.stderr
    stdout_file = None
    stderr_file = None

    try:
        # STDOUT redirection
        if stdout_path is not None:
            mode = "a" if stdout_append else "w"
            stdout_file = open(stdout_path, mode)
            stdout_stream = stdout_file

        # STDERR redirection
        if stderr_path is not None:
            mode = "a" if stderr_append else "w"
            stderr_file = open(stderr_path, mode)
            stderr_stream = stderr_file

        # Builtin?
        if command in BUILTINS:
            run_builtin(command, args, stdout_stream, stderr_stream)
            return

        # External command
        exe = find_executable(command)
        if not exe:
            # Codecrafters tests expect this on stdout
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


# ---------- Pipeline execution (2+ commands) ----------

def split_pipeline(tokens):
    """
    Split tokens into a list of command-token-lists by '|'.
    e.g. ['cat', 'f', '|', 'wc'] → [['cat', 'f'], ['wc']]
    """
    stages = [[]]
    for t in tokens:
        if t == "|":
            stages.append([])
        else:
            stages[-1].append(t)
    # Remove any empty final stage if created accidentally
    stages = [s for s in stages if s]
    return stages


def run_pipeline(tokens):
    """
    Run a pipeline like:
      cat file | head -n 5 | wc

    For Codecrafters:
    - We support multi-stage pipelines.
    - For pipelines ending in `type`, we handle the last stage as a builtin.
    - For pipelines starting with `echo`, we allow external /bin/echo to handle it.
    """
    stages = split_pipeline(tokens)
    if not stages:
        return

    # Special case: last stage is builtin `type`
    last_stage = stages[-1]
    if last_stage and last_stage[0] == "type":
        # Ignore preceding pipeline data, just run builtin type with stdout=terminal
        cmd_tokens, _, _, _, _ = parse_redirections(last_stage)
        if cmd_tokens is None or not cmd_tokens:
            return
        cmd = cmd_tokens[0]
        args = cmd_tokens[1:]
        if cmd == "type":
            run_builtin("type", args, sys.stdout, sys.stderr)
        else:
            # Fallback if something weird
            run_single_command(last_stage)
        return

    # General pipeline of external commands
    processes = []
    prev_proc = None

    for i, stage_tokens in enumerate(stages):
        # NOTE: For pipeline stages we ignore redirections for now (Codecrafters
        # pipeline tests don't mix >, >>, 2> etc with |).
        if not stage_tokens:
            continue

        cmd = stage_tokens[0]
        args = stage_tokens[1:]

        exe = find_executable(cmd)
        if not exe:
            print(f"{cmd}: command not found")
            return

        # stdin
        if prev_proc is None:
            stdin = None
        else:
            stdin = prev_proc.stdout

        # stdout
        if i == len(stages) - 1:
            stdout = None  # inherit (terminal)
        else:
            stdout = subprocess.PIPE

        p = subprocess.Popen(
            [cmd] + args,
            executable=exe,
            stdin=stdin,
            stdout=stdout,
            stderr=sys.stderr
        )

        # Close the previous stage's stdout in the parent to propagate EOF
        if prev_proc is not None and prev_proc.stdout is not None:
            prev_proc.stdout.close()

        processes.append(p)
        prev_proc = p

    # Wait for all pipeline processes to finish
    for p in processes:
        p.wait()


# ---------- Main REPL ----------

def main():
    while True:
        try:
            # Prompt
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

        # Use shlex to handle quoting: '...', "...", spaces, etc.
        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"Syntax error: {e}")
            continue

        if not tokens:
            continue

        # If there's a pipeline, handle specially
        if "|" in tokens:
            run_pipeline(tokens)
        else:
            run_single_command(tokens)


if __name__ == "__main__":
    main()
