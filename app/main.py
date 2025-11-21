import os
import sys
import shlex
import subprocess

# -------------------------
# Builtins
# -------------------------

BUILTINS = {"exit", "echo", "type", "pwd", "cd"}


def find_executable(command: str):
    """Search current directory and PATH for an executable."""
    # Case 1: Direct path (contains '/')
    if "/" in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        return None

    # Case 2: Current directory
    cwd_path = os.path.join(os.getcwd(), command)
    if os.path.isfile(cwd_path) and os.access(cwd_path, os.X_OK):
        return cwd_path

    # Case 3: PATH
    path_env = os.environ.get("PATH", "")
    for directory in path_env.split(":"):
        if not directory:
            continue
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


def builtin_exit(args, stdin, stdout, stderr):
    code = 0
    if args:
        try:
            code = int(args[0])
        except ValueError:
            stderr.write(f"exit: {args[0]}: numeric argument required\n")
            stderr.flush()
            code = 1
    sys.exit(code)


def builtin_echo(args, stdin, stdout, stderr):
    stdout.write(" ".join(args) + "\n")
    stdout.flush()


def builtin_pwd(args, stdin, stdout, stderr):
    stdout.write(os.getcwd() + "\n")
    stdout.flush()


def builtin_cd(args, stdin, stdout, stderr):
    if not args:
        path_arg = os.path.expanduser("~")
        display_path = path_arg
    else:
        display_path = args[0]
        path_arg = os.path.expanduser(args[0])

    if not os.path.isabs(path_arg):
        path_arg = os.path.abspath(os.path.join(os.getcwd(), path_arg))

    try:
        os.chdir(path_arg)
    except FileNotFoundError:
        stderr.write(f"cd: {display_path}: No such file or directory\n")
        stderr.flush()


def builtin_type(args, stdin, stdout, stderr):
    if not args:
        stderr.write("type: missing argument\n")
        stderr.flush()
        return

    target = args[0]
    if target in BUILTINS:
        stdout.write(f"{target} is a shell builtin\n")
        stdout.flush()
        return

    exe = find_executable(target)
    if exe:
        stdout.write(f"{target} is {exe}\n")
    else:
        stdout.write(f"{target}: not found\n")
    stdout.flush()


def run_builtin(command, args, stdin, stdout, stderr):
    if command == "exit":
        builtin_exit(args, stdin, stdout, stderr)
    elif command == "echo":
        builtin_echo(args, stdin, stdout, stderr)
    elif command == "pwd":
        builtin_pwd(args, stdin, stdout, stderr)
    elif command == "cd":
        builtin_cd(args, stdin, stdout, stderr)
    elif command == "type":
        builtin_type(args, stdin, stdout, stderr)
    else:
        # Should not happen if we check BUILTINS before calling
        stdout.write(f"{command}: command not found\n")
        stdout.flush()


# -------------------------
# Redirection parsing
# -------------------------

class CommandSpec:
    def __init__(self, argv, stdout_redir=None, stderr_redir=None):
        self.argv = argv              # list[str]
        self.stdout_redir = stdout_redir  # (mode, path) or None; mode in {"overwrite", "append"}
        self.stderr_redir = stderr_redir  # same as above


def parse_redirections(tokens):
    """
    Parse a single command's tokens into argv + redirection info.
    Supports: >, 1>, >>, 1>>, 2>, 2>>.
    """
    argv = []
    stdout_redir = None
    stderr_redir = None
    i = 0
    error = False

    while i < len(tokens):
        t = tokens[i]
        if t in (">", "1>"):
            if i + 1 >= len(tokens):
                print("syntax error: expected filename after >", file=sys.stderr)
                error = True
                break
            stdout_redir = ("overwrite", tokens[i + 1])
            i += 2
        elif t in (">>", "1>>"):
            if i + 1 >= len(tokens):
                print("syntax error: expected filename after >>", file=sys.stderr)
                error = True
                break
            stdout_redir = ("append", tokens[i + 1])
            i += 2
        elif t == "2>":
            if i + 1 >= len(tokens):
                print("syntax error: expected filename after 2>", file=sys.stderr)
                error = True
                break
            stderr_redir = ("overwrite", tokens[i + 1])
            i += 2
        elif t == "2>>":
            if i + 1 >= len(tokens):
                print("syntax error: expected filename after 2>>", file=sys.stderr)
                error = True
                break
            stderr_redir = ("append", tokens[i + 1])
            i += 2
        else:
            argv.append(t)
            i += 1

    return CommandSpec(argv, stdout_redir, stderr_redir), error


# -------------------------
# Command execution
# -------------------------

def open_redir_stream(redir_spec, default_stream):
    """
    redir_spec: (mode, path) or None
    Returns (stream, opened_file_or_None)
    """
    if redir_spec is None:
        return default_stream, None

    mode, path = redir_spec
    file_mode = "w" if mode == "overwrite" else "a"
    f = open(path, file_mode)
    return f, f


def run_single_command(spec: CommandSpec):
    if not spec.argv:
        return

    command = spec.argv[0]
    args = spec.argv[1:]

    # Setup redirections
    out_stream, out_file = open_redir_stream(spec.stdout_redir, sys.stdout)
    err_stream, err_file = open_redir_stream(spec.stderr_redir, sys.stderr)

    try:
        if command in BUILTINS:
            run_builtin(command, args, sys.stdin, out_stream, err_stream)
        else:
            exe = find_executable(command)
            if not exe:
                # "command not found" usually goes to stdout in our previous stages
                out_stream.write(f"{command}: command not found\n")
                out_stream.flush()
                return

            subprocess.run(
                [command] + args,
                executable=exe,
                stdin=sys.stdin,
                stdout=out_stream,
                stderr=err_stream,
            )
    finally:
        if out_file is not None:
            out_file.close()
        if err_file is not None and err_file is not out_file:
            err_file.close()


def run_pipeline(spec1: CommandSpec, spec2: CommandSpec):
    """
    Execute spec1 | spec2
    Supports builtins + externals, and redirection on:
      - spec1: stderr only
      - spec2: stdout + stderr.
    """
    if not spec1.argv or not spec2.argv:
        return

    cmd1, args1 = spec1.argv[0], spec1.argv[1:]
    cmd2, args2 = spec2.argv[0], spec2.argv[1:]

    is_builtin1 = cmd1 in BUILTINS
    is_builtin2 = cmd2 in BUILTINS

    # Redirections: stdout of first is always piped, so ignore spec1.stdout_redir.
    # stderr of both and stdout of second are respected.
    out2_stream, out2_file = open_redir_stream(spec2.stdout_redir, sys.stdout)
    err1_stream, err1_file = open_redir_stream(spec1.stderr_redir, sys.stderr)
    err2_stream, err2_file = open_redir_stream(spec2.stderr_redir, sys.stderr)

    try:
        if not is_builtin1 and not is_builtin2:
            # external | external
            exe1 = find_executable(cmd1)
            exe2 = find_executable(cmd2)
            if not exe1:
                err1_stream.write(f"{cmd1}: command not found\n")
                err1_stream.flush()
                return
            if not exe2:
                err2_stream.write(f"{cmd2}: command not found\n")
                err2_stream.flush()
                return

            p1 = subprocess.Popen(
                [cmd1] + args1,
                executable=exe1,
                stdin=sys.stdin,
                stdout=subprocess.PIPE,
                stderr=err1_stream,
                text=True,
            )
            p2 = subprocess.Popen(
                [cmd2] + args2,
                executable=exe2,
                stdin=p1.stdout,
                stdout=out2_stream,
                stderr=err2_stream,
                text=True,
            )
            if p1.stdout is not None:
                p1.stdout.close()
            p2.communicate()
            # For commands like `tail -f`, ensure p1 doesn't linger
            try:
                p1.terminate()
            except Exception:
                pass

        elif is_builtin1 and not is_builtin2:
            # builtin | external
            exe2 = find_executable(cmd2)
            if not exe2:
                err2_stream.write(f"{cmd2}: command not found\n")
                err2_stream.flush()
                return

            p2 = subprocess.Popen(
                [cmd2] + args2,
                executable=exe2,
                stdin=subprocess.PIPE,
                stdout=out2_stream,
                stderr=err2_stream,
                text=True,
            )

            # Run builtin, writing into p2.stdin
            run_builtin(cmd1, args1, sys.stdin, p2.stdin, err1_stream)
            if p2.stdin is not None:
                p2.stdin.close()
            p2.communicate()

        elif not is_builtin1 and is_builtin2:
            # external | builtin
            exe1 = find_executable(cmd1)
            if not exe1:
                err1_stream.write(f"{cmd1}: command not found\n")
                err1_stream.flush()
                return

            p1 = subprocess.Popen(
                [cmd1] + args1,
                executable=exe1,
                stdin=sys.stdin,
                stdout=subprocess.PIPE,
                stderr=err1_stream,
                text=True,
            )

            # Our builtins (echo, type, etc.) don't currently read stdin,
            # but we pass it in case future stages do.
            stdin_for_builtin = p1.stdout if p1.stdout is not None else sys.stdin
            run_builtin(cmd2, args2, stdin_for_builtin, out2_stream, err2_stream)

            if p1.stdout is not None:
                p1.stdout.close()
            try:
                p1.terminate()
            except Exception:
                pass

        else:
            # builtin | builtin (not needed for tests, but handle gracefully)
            # Pipe is not really used since our builtins ignore stdin.
            run_builtin(cmd1, args1, sys.stdin, sys.stdout, sys.stderr)
            run_builtin(cmd2, args2, sys.stdin, out2_stream, err2_stream)

    finally:
        if out2_file is not None:
            out2_file.close()
        if err1_file is not None and err1_file is not out2_file:
            err1_file.close()
        if err2_file is not None and err2_file not in (out2_file, err1_file):
            err2_file.close()


# -------------------------
# REPL
# -------------------------

def split_pipeline(tokens):
    """Split tokens on '|' into up to two segments (we only support a single pipe)."""
    segments = []
    current = []
    for t in tokens:
        if t == "|":
            segments.append(current)
            current = []
        else:
            current.append(t)
    segments.append(current)
    return segments


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
            print(f"Syntax error: {e}", file=sys.stderr)
            continue

        if not tokens:
            continue

        # Check for pipeline
        if "|" in tokens:
            segments = split_pipeline(tokens)
            if len(segments) != 2:
                # For this challenge only 2-command pipelines are needed
                print("pipelines with more than one '|' are not supported", file=sys.stderr)
                continue

            spec1, err1 = parse_redirections(segments[0])
            spec2, err2 = parse_redirections(segments[1])
            if err1 or err2 or not spec1.argv or not spec2.argv:
                continue

            run_pipeline(spec1, spec2)
        else:
            spec, err = parse_redirections(tokens)
            if err or not spec.argv:
                continue
            run_single_command(spec)


if __name__ == "__main__":
    main()
