import os
import shlex
import subprocess
import shutil
from typing import Tuple, List
import readline
import signal

last_completion_text = ""
completion_count = 0
command_history = []


def get_executable_commands(text: str) -> List[str]:
    commands = []
    path_env = os.environ.get("PATH", "")
    if not path_env:
        return commands
    path_dirs = path_env.split(os.pathsep)

    for path_dir in path_dirs:
        if not os.path.isdir(path_dir):
            continue

        try:
            for filename in os.listdir(path_dir):
                if filename.startswith(text):
                    full_path = os.path.join(path_dir, filename)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        if filename not in commands:
                            commands.append(filename)
        except (OSError, PermissionError):
            continue

    return sorted(commands)


def get_all_matches(text):
    builtins = ["exit"]
    builtin_matches = [cmd for cmd in builtins if cmd.startswith(text)]
    external_matches = get_executable_commands(text)
    # print(builtin_matches + external_matches)
    return builtin_matches + external_matches


def find_common_prefix(strings: List[str]) -> str:
    if not strings:
        return ""

    if len(strings) == 1:
        return strings[0]

    prefix = strings[0]
    for string in strings[1:]:
        common_len = 0
        min_len = min(len(prefix), len(string))

        for i in range(min_len):
            if prefix[i] == string[i]:
                common_len += 1
            else:
                break

        prefix = prefix[:common_len]

        if not prefix:
            break

    return prefix


def complete_builtin(text, state):
    global last_completion_text, completion_count
    if text != last_completion_text or state == 0:
        if text != last_completion_text:
            completion_count = 0
        last_completion_text = text
    all_matches = get_all_matches(text)
    if not all_matches:
        return None
    if len(all_matches) == 1:
        if state == 0:
            return all_matches[0] + " "
        return None
    if len(all_matches) > 1:
        if state == 0:
            completion_count += 1
            common_prefix = find_common_prefix(all_matches)
            if len(common_prefix) > len(text):
                return common_prefix
            if completion_count == 1:
                print("\a", end="")
                return None
            elif completion_count == 2:
                print()
                print("  ".join(all_matches))
                print("$ " + text, end="")
                return None
        return None
    return None


def setup_readline():
    readline.set_completer(complete_builtin)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n`!@#$%^&*()=+[{]}\\|;:'\",<>?")
    readline.parse_and_bind("set show-all-if-ambiguous off")
    readline.parse_and_bind("set completion-query-items -1")
    readline.set_auto_history(False)


class BuiltIn:
    def execute(self, args: str = ""):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class BuiltinFactory:
    builtins = {}

    @staticmethod
    def create(command: str):
        return BuiltinFactory.builtins.get(command, lambda: None)()

    @staticmethod
    def is_builtin(command: str) -> bool:
        return command in BuiltinFactory.builtins


class Exit(BuiltIn):
    def execute(self, args: str = ""):
        exit(0)

    def __str__(self):
        return "exit is a shell builtin"


class Echo(BuiltIn):
    def execute(self, args: str = ""):
        print(args)

    def __str__(self):
        return "echo is a shell builtin"


class PWD(BuiltIn):
    def execute(self, args: str = ""):
        print(os.getcwd())

    def __str__(self):
        return "pwd is a shell builtin"


class CD(BuiltIn):
    def execute(self, args: str = ""):
        path = args.strip()

        if path == "~":
            path = os.environ.get("HOME", "")

        if not path:
            return

        try:
            os.chdir(path)
        except FileNotFoundError:
            print(f"cd: {args}: No such file or directory", file=os.sys.stderr)
        except Exception as e:
            print(f"cd: {args}: {e}", file=os.sys.stderr)

    def __str__(self):
        return "cd: a shell builtin that changes the current directory"


class TypeExplain(BuiltIn):
    def execute(self, args: str = ""):
        if not args:
            print("type: usage: type [name ...]")
            return

        for token in shlex.split(args):
            if token in ["exit", "pwd", "cd", "type", "echo", "history"]:
                print(token, "is a shell builtin")
            else:
                path = self.find_in_path(token)
                if path:
                    print(f"{token} is {path}")
                else:
                    print(f"{token}: not found")

    def find_in_path(self, cmd: str) -> str:
        for dir in os.environ.get("PATH", "").split(":"):
            full_path = os.path.join(dir, cmd)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                return full_path
        return ""

    def __str__(self):
        return "type is a shell builtin"


class History(BuiltIn):
    def execute(self, args: str = ""):
        global command_history
        if args.strip():
            n = int(args.strip())
            histories = command_history[-n:]
            start_index = len(command_history) - n + 1
        else:
            histories = command_history
            start_index = 1

        for i, cmd in enumerate(histories, start_index):
            print(f"    {i}  {cmd}")

    def __str__(self):
        return "history is a shell builtin"


BuiltinFactory.builtins = {
    "exit": Exit,
    # "echo": Echo,
    "pwd": PWD,
    "cd": CD,
    "type": TypeExplain,
    "history": History,
}


def parse_input(input_str: str) -> Tuple[str, str, List[str]]:
    tokens = shlex.split(input_str, posix=True)
    command = tokens[0] if tokens else ""
    args = " ".join(tokens[1:])
    return command, args, tokens


def parse_pipeline(input_str: str) -> List[str]:
    """Parse a command string into pipeline components."""
    # Split by pipe, but handle quoted strings properly
    commands = []
    current_cmd = ""
    in_quotes = False
    quote_char = None

    i = 0
    while i < len(input_str):
        char = input_str[i]

        if char in ['"', "'"] and not in_quotes:
            in_quotes = True
            quote_char = char
            current_cmd += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
            current_cmd += char
        elif char == "|" and not in_quotes:
            commands.append(current_cmd.strip())
            current_cmd = ""
        else:
            current_cmd += char

        i += 1

    if current_cmd.strip():
        commands.append(current_cmd.strip())

    return commands


def execute_builtin_in_pipeline(command: str, args: str, stdin_fd=None, stdout_fd=None):
    pid = os.fork()
    if pid == 0:
        if stdin_fd is not None:
            os.dup2(stdin_fd, 0)

        if stdout_fd is not None:
            os.dup2(stdout_fd, 1)

        builtin = BuiltinFactory.create(command)
        if builtin:
            builtin.execute(args)

        os._exit(0)
    else:
        return pid


def execute_pipeline(commands: List[str]):
    if len(commands) == 1:
        run_single_command(commands[0])
        return

    pipes = []
    for i in range(len(commands) - 1):
        r_fd, w_fd = os.pipe()
        pipes.append((r_fd, w_fd))

    processes = []

    try:
        for i, cmd in enumerate(commands):
            command, args, tokens = parse_input(cmd)

            stdin_fd = pipes[i - 1][0] if i > 0 else None
            stdout_fd = pipes[i][1] if i < len(commands) - 1 else None

            if BuiltinFactory.is_builtin(command):
                pid = execute_builtin_in_pipeline(command, args, stdin_fd, stdout_fd)
                processes.append(pid)
                continue

            path = shutil.which(command)
            if not path:
                print(f"{command}: command not found")
                # Clean up pipes and processes
                for r_fd, w_fd in pipes:
                    try:
                        os.close(r_fd)
                        os.close(w_fd)
                    except:
                        pass
                for pid in processes:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        os.waitpid(pid, 0)
                    except:
                        pass
                return

            pid = os.fork()
            if pid == 0:
                if stdin_fd is not None:
                    os.dup2(stdin_fd, 0)

                if stdout_fd is not None:
                    os.dup2(stdout_fd, 1)

                for r_fd, w_fd in pipes:
                    try:
                        os.close(r_fd)
                        os.close(w_fd)
                    except:
                        pass

                try:
                    os.execv(path, tokens)
                except Exception as e:
                    print(f"Error executing {command}: {e}")
                    os._exit(1)
            else:
                processes.append(pid)

        for r_fd, w_fd in pipes:
            try:
                os.close(r_fd)
                os.close(w_fd)
            except:
                pass

        for pid in processes:
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass

    except Exception as e:
        print(f"Pipeline error: {e}")
        for r_fd, w_fd in pipes:
            try:
                os.close(r_fd)
                os.close(w_fd)
            except:
                pass
        for pid in processes:
            try:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)
            except:
                pass


def run_single_command(input_str: str):
    stdout_file = None
    stderr_file = None
    stdout_append = False
    stderr_append = False

    if "2>>" in input_str:
        parts = input_str.split("2>>")
        cmd_part = parts[0].strip()
        stderr_file = parts[1].strip() if len(parts) > 1 else ""
        stderr_append = True
        input_str = cmd_part
    elif "2>" in input_str:
        parts = input_str.split("2>")
        cmd_part = parts[0].strip()
        stderr_file = parts[1].strip() if len(parts) > 1 else ""
        stderr_append = False
        input_str = cmd_part

    if "1>>" in input_str:
        parts = input_str.split("1>>")
        cmd_part = parts[0].strip()
        stdout_file = parts[1].strip() if len(parts) > 1 else ""
        stdout_append = True
    elif "1>" in input_str:
        parts = input_str.split("1>")
        cmd_part = parts[0].strip()
        stdout_file = parts[1].strip() if len(parts) > 1 else ""
        stdout_append = False
    elif ">>" in input_str:
        parts = input_str.split(">>")
        cmd_part = parts[0].strip()
        stdout_file = parts[1].strip() if len(parts) > 1 else ""
        stdout_append = True
    elif ">" in input_str:
        parts = input_str.split(">")
        cmd_part = parts[0].strip()
        stdout_file = parts[1].strip() if len(parts) > 1 else ""
        stdout_append = False
    else:
        cmd_part = input_str

    command, args, tokens = parse_input(cmd_part)
    if not command:
        return

    if BuiltinFactory.is_builtin(command):
        original_stdout = None
        original_stderr = None

        try:
            if stdout_file:
                original_stdout = os.dup(1)
                stdout_handle = open(stdout_file, "a" if stdout_append else "w")
                os.dup2(stdout_handle.fileno(), 1)
                stdout_handle.close()

            if stderr_file:
                original_stderr = os.dup(2)
                stderr_handle = open(stderr_file, "a" if stderr_append else "w")
                os.dup2(stderr_handle.fileno(), 2)
                stderr_handle.close()

            builtin = BuiltinFactory.create(command)
            if builtin:
                builtin.execute(args)

        finally:
            if original_stdout is not None:
                os.dup2(original_stdout, 1)
                os.close(original_stdout)
            if original_stderr is not None:
                os.dup2(original_stderr, 2)
                os.close(original_stderr)
        return

    path = shutil.which(command)
    if not path:
        print(f"{command}: command not found")
        return

    try:
        stdout_handle = None
        stderr_handle = None

        if stdout_file:
            stdout_handle = open(stdout_file, "a" if stdout_append else "w")
        if stderr_file:
            stderr_handle = open(stderr_file, "a" if stderr_append else "w")
        subprocess.run(
            tokens,
            stdout=stdout_handle if stdout_handle else None,
            stderr=stderr_handle if stderr_handle else None,
        )

        if stdout_handle:
            stdout_handle.close()
        if stderr_handle:
            stderr_handle.close()

    except Exception as e:
        print(f"Error: {e}")


def run_external_command(input_str: str):
    if "|" in input_str:
        commands = parse_pipeline(input_str)
        execute_pipeline(commands)
    else:
        run_single_command(input_str)


# Shell loop
if __name__ == "__main__":
    setup_readline()
    while True:
        try:
            last_completion_text = ""
            completion_count = 0
            input_str = input("$ ").strip()
            if not input_str:
                continue
            readline.add_history(input_str)
            command_history.append(input_str)

            if "|" in input_str:
                run_external_command(input_str)
            else:
                [command, args, tokens] = parse_input(input_str)
                if BuiltinFactory.is_builtin(command):
                    builtin = BuiltinFactory.create(command)
                    if builtin:
                        builtin.execute(args)
                else:
                    run_external_command(input_str)
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
