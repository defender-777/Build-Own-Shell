import sys
import os
import shlex
import subprocess
import io
from contextlib import redirect_stdout, redirect_stderr, contextmanager

try:
    import readline  # Works on Linux/macOS
except ImportError:
    try:
        import pyreadline as readline  # For older pyreadline
    except ImportError:
        try:
            import pyreadline3 as readline  # For pyreadline3 (Python 3+)
        except ImportError:
            readline = None


class Shell:
    def __init__(self):
        self.commands_map = {
            "exit": self.execute_exit,
            "echo": self.execute_echo,
            "type": self.execute_type,
            "pwd": self.execute_pwd,
            "cd": self.execute_cd,
            "history": self.execute_history,
        }
        self.continue_repl = True
        self.command_history = []
        self.last_history_append = 0
        self.all_commands = set(self.commands_map.keys())
        self.refresh_external_commands()
        self.setup_autocomplete()

    def refresh_external_commands(self):
        self.external_commands = self.get_executables_in_path()
        self.all_commands = set(self.commands_map.keys()) | self.external_commands

    def get_executables_in_path(self):
        paths = os.environ.get("PATH", "").split(os.pathsep)
        executables = set()

        if os.name == "nt":
            # Windows: consider PATHEXT
            pathext = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").lower().split(";")

            for directory in paths:
                if not os.path.isdir(directory):
                    continue

                for filename in os.listdir(directory):
                    full_path = os.path.join(directory, filename)

                    if os.path.isfile(full_path):
                        _, ext = os.path.splitext(filename)

                        if ext.lower() in pathext:
                            executables.add(filename)
        else:
            # Unix-like: any file with execute permission
            for directory in paths:
                if not os.path.isdir(directory):
                    continue

                for filename in os.listdir(directory):
                    full_path = os.path.join(directory, filename)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        executables.add(filename)

        return executables

    def setup_autocomplete(self):
        if readline:
            # Set up autocompletion as before
            def completer(text, state):
                options = [cmd for cmd in self.all_commands if cmd.startswith(text)]

                if state < len(options):
                    # Only add a space if the completion is unique and not already present
                    completion = options[state]

                    if len(options) == 1 and completion != text:
                        return completion + " "

                    return completion

                return None

            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
        else:
            print("Warning: No readline support. Autocompletion is disabled.")

    def parse_command(self, command_str):
        return shlex.split(command_str)

    def parse_redirection(self, args):
        stdout_file = None
        stdout_mode = None
        stderr_file = None
        stderr_mode = None
        new_args = []
        i = 0

        while i < len(args):
            if args[i] == ">" or args[i] == "1>":
                if i + 1 < len(args):
                    stdout_file = args[i + 1]
                    stdout_mode = "w"
                    i += 2
                    continue
            elif args[i] == ">>" or args[i] == "1>>":
                if i + 1 < len(args):
                    stdout_file = args[i + 1]
                    stdout_mode = "a"
                    i += 2
                    continue
            elif args[i] == "2>":
                if i + 1 < len(args):
                    stderr_file = args[i + 1]
                    stderr_mode = "w"
                    i += 2
                    continue
            elif args[i] == "2>>":
                if i + 1 < len(args):
                    stderr_file = args[i + 1]
                    stderr_mode = "a"
                    i += 2
                    continue
            else:
                new_args.append(args[i])

            i += 1

        return new_args, stdout_file, stdout_mode, stderr_file, stderr_mode

    @contextmanager
    def dummy_cm(self):
        yield

    def find_executable(self, command_name):
        # On Windows, try with PATHEXT if not found directly
        paths = os.environ.get("PATH", "").split(os.pathsep)

        if os.name == "nt":
            pathext = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").lower().split(";")

            for directory in paths:
                if not os.path.isdir(directory):
                    continue

                for ext in pathext:
                    full_path = os.path.join(directory, command_name)

                    if not full_path.lower().endswith(ext):
                        full_path_ext = full_path + ext
                    else:
                        full_path_ext = full_path

                    if os.path.isfile(full_path_ext):
                        return full_path_ext
        else:
            for directory in paths:
                full_path = os.path.join(directory, command_name)

                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    return full_path

        return None

    def run_executable(
        self, executable_path, arguments, stdout_file=None, stderr_file=None
    ):
        kwargs = {"text": True}

        if stdout_file:
            kwargs["stdout"] = stdout_file
        else:
            kwargs["stdout"] = subprocess.PIPE

        if stderr_file:
            kwargs["stderr"] = stderr_file
        else:
            kwargs["stderr"] = subprocess.PIPE

        result = subprocess.run(arguments, executable=executable_path, **kwargs)

        if not stdout_file and result.stdout:
            sys.stdout.write(result.stdout)

        if not stderr_file and result.stderr:
            sys.stderr.write(result.stderr)

    # Built-in command implementations
    def execute_exit(self, args):
        status_code = args[1] if len(args) > 1 else "0"

        if status_code == "0":
            self.continue_repl = False

    def execute_echo(self, args):
        print(" ".join(args[1:]))

    def execute_history(self, args):
        try:
            functional_parameter = args[1]
        except IndexError:
            functional_parameter = ""

        try:
            file_path = args[2]
        except IndexError:
            file_path = None

        if functional_parameter == "-r" and file_path is not None:
            self.read_history(file_path)
        elif functional_parameter == "-w" and file_path is not None:
            self.write_history(file_path)
        elif functional_parameter == "-a" and file_path is not None:
            self.append_history(file_path)
        else:
            self.list_history(functional_parameter)

    def read_history(self, file_path):
        if readline and hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(file_path)
            except Exception as e:
                pass
                # print(f"Error reading history file: {e}")
        else:
            # Fallback: load into self.command_history if you want
            try:
                with open(file_path, "r") as f:
                    for line in f:
                        self.command_history.append(line.rstrip("\n"))
            except Exception as e:
                pass
                # print(f"Error reading history file: {e}")

        self.last_history_append = self.get_history_length()

    def write_history(self, file_path):
        if readline and hasattr(readline, "write_history_file"):
            try:
                readline.write_history_file(file_path)
            except Exception as e:
                pass
                # print(f"Error writing history file: {e}")
        else:
            # Fallback: save self.command_history
            try:
                with open(file_path, "w") as f:
                    for cmd in self.command_history:
                        f.write(cmd + "\n")
            except Exception as e:
                pass
                # print(f"Error writing history file: {e}")

        self.last_history_append = self.get_history_length()

    def get_history_length(self):
        if readline and hasattr(readline, "get_history_item"):
            return readline.get_current_history_length()
        else:
            return len(self.command_history)

    def append_history(self, file_path):
        total = self.get_history_length()

        if readline and hasattr(readline, "get_history_item"):
            try:
                with open(file_path, "a") as f:
                    for i in range(self.last_history_append, total):
                        cmd = readline.get_history_item(i + 1)
                        if cmd is not None:
                            f.write(cmd + "\n")
                self.last_history_append = total
            except Exception as e:
                pass
                # print(f"Error appending history file: {e}")
        else:
            try:
                with open(file_path, "a") as f:
                    for i in range(self.last_history_append, total):
                        f.write(self.command_history[i] + "\n")
                self.last_history_append = total
            except Exception as e:
                pass
                # print(f"Error appending history file: {e}")

    def list_history(self, n):
        if readline and hasattr(readline, "get_history_item"):
            total = readline.get_current_history_length()
            get_item = lambda i: readline.get_history_item(i + 1)
        else:
            total = len(self.command_history)
            get_item = lambda i: self.command_history[i]

        try:
            entry_limiter = int(n)
        except Exception:
            entry_limiter = total

        start_entry = total - entry_limiter
        if start_entry < 0:
            start_entry = 0

        for i in range(start_entry, total):
            cmd = get_item(i)
            print(f"    {i+1}  {cmd}")

    def execute_type(self, args):
        if len(args) < 2:
            print("type: missing argument")

        type_target = args[1]

        if type_target in self.commands_map:
            print(f"{type_target} is a shell builtin")
        else:
            path_directory = self.find_executable(type_target)

            if path_directory is None:
                print(f"{type_target}: not found")
            else:
                print(f"{type_target} is {path_directory}")

    def execute_pwd(self, args):
        print(os.getcwd())

    def execute_cd(self, args):
        if len(args) < 2:
            print("cd: missing argument")

        cd_target = args[1]

        try:
            os.chdir(os.path.expanduser(cd_target))
        except FileNotFoundError:
            print(f"cd: {cd_target}: No such file or directory")

    def old_main_loop(self):
        while self.continue_repl:
            try:
                command = input("$ ")
            except EOFError:
                print()
                break

            parsed_command = self.parse_command(command)
            parsed_command, stdout_file, stdout_mode, stderr_file, stderr_mode = (
                self.parse_redirection(parsed_command)
            )

            if not parsed_command:
                continue

            command_keyword = parsed_command[0]

            stdout_cm = open(stdout_file, stdout_mode) if stdout_file else None
            stderr_cm = open(stderr_file, stderr_mode) if stderr_file else None

            try:
                with redirect_stdout(stdout_cm) if stdout_cm else self.dummy_cm(), (
                    redirect_stderr(stderr_cm) if stderr_cm else self.dummy_cm()
                ):
                    if command_keyword in self.commands_map:
                        try:
                            self.commands_map[command_keyword](parsed_command)
                        except Exception:
                            print("Invalid command")
                    else:
                        path_directory = self.find_executable(command_keyword)

                        if path_directory is None:
                            print(f"{command}: command not found")
                        else:
                            try:
                                self.run_executable(
                                    path_directory,
                                    parsed_command,
                                    stdout_file=stdout_cm,
                                    stderr_file=stderr_cm,
                                )
                            except Exception:
                                print("Invalid command")
            finally:
                if stdout_cm:
                    stdout_cm.close()
                if stderr_cm:
                    stderr_cm.close()

    def main_loop(self):
        while self.continue_repl:
            try:
                command = input("$ ")
            except EOFError:
                print()
                break

            # add command to history
            self.command_history.append(command)
            # RUn command through pipeline
            self.run_pipeline(command)

    def run_pipeline(self, command_line):
        segments = [seg.strip() for seg in command_line.split("|")]
        num_segments = len(segments)
        prev_output = None
        processes = []
        stdout_cm = None
        stderr_cm = None

        for i, segment in enumerate(segments):
            is_last = i == num_segments - 1
            parsed_command = self.parse_command(segment)
            # Only parse redirection on last segment
            if is_last:
                parsed_command, stdout_file, stdout_mode, stderr_file, stderr_mode = (
                    self.parse_redirection(parsed_command)
                )
                if stdout_file:
                    stdout_cm = open(stdout_file, stdout_mode)
                if stderr_file:
                    stderr_cm = open(stderr_file, stderr_mode)
            if not parsed_command:
                return
            # command name
            command_keyword = parsed_command[0]
            # Built-in
            if command_keyword in self.commands_map:
                input_stream = prev_output if prev_output else None
                output_stream = (
                    io.StringIO()
                    if not is_last
                    else (stdout_cm if stdout_cm else sys.stdout)
                )
                error_stream = stderr_cm if is_last and stderr_cm else sys.stderr
                orig_stdin = sys.stdin
                orig_stdout = sys.stdout
                orig_stderr = sys.stderr
                try:
                    if input_stream:
                        if (
                            hasattr(input_stream, "seekable")
                            and input_stream.seekable()
                        ):
                            input_stream.seek(0)
                        sys.stdin = input_stream
                    sys.stdout = output_stream
                    sys.stderr = error_stream
                    self.commands_map[command_keyword](parsed_command)
                finally:
                    sys.stdin = orig_stdin
                    sys.stdout = orig_stdout
                    sys.stderr = orig_stderr
                if not is_last:
                    # If next is external, use a real pipe
                    next_is_external = False
                    if i + 1 < num_segments:
                        next_cmd = self.parse_command(segments[i + 1])
                        if next_cmd and next_cmd[0] not in self.commands_map:
                            next_is_external = True
                    if next_is_external:
                        r, w = os.pipe()
                        wfile = os.fdopen(w, "w")
                        orig_stdout = sys.stdout
                        try:
                            sys.stdout = wfile
                            self.commands_map[command_keyword](parsed_command)
                        finally:
                            sys.stdout = orig_stdout
                            wfile.close()
                        prev_output = os.fdopen(r)
                    else:
                        output_stream.seek(0)
                        prev_output = output_stream
            else:
                # External
                path_directory = self.find_executable(command_keyword)
                if path_directory is None:
                    print(f"{command_keyword}: command not found")
                    return
                if prev_output is not None:
                    stdin = prev_output
                else:
                    stdin = None
                stdout = (
                    stdout_cm
                    if is_last and stdout_cm
                    else (subprocess.PIPE if not is_last else None)
                )
                stderr = stderr_cm if is_last and stderr_cm else None
                try:
                    proc = subprocess.Popen(
                        parsed_command,
                        executable=path_directory,
                        stdin=stdin,
                        stdout=stdout,
                        stderr=stderr,
                        text=True,
                    )
                    if not is_last:
                        prev_output = proc.stdout
                    processes.append(proc)
                except Exception:
                    print("Invalid command")
                    return
        for proc in processes:
            proc.wait()
        if stdout_cm:
            stdout_cm.close()
        if stderr_cm:
            stderr_cm.close()


def main():
    shell = Shell()
    histfile = os.environ.get("HISTFILE")

    if histfile:
        shell.read_history(histfile)

    shell.main_loop()

    if histfile:
        shell.append_history(histfile)


if __name__ == "__main__":
    main()