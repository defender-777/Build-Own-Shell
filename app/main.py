import sys
import os
import subprocess
import shutil
import shlex

try:
    import readline
except ImportError:
    import pyreadline3 as readline


# Variables to track completion state
last_tab_text = ""
last_tab_matches = []
last_tab_count = 0

# Set up tab completion


def find_executable(command):
    """Find executable in PATH directories. Returns full path if found, None otherwise."""
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for directory in path_dirs:
        full_path = os.path.join(directory, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None


def find_all_executables():
    """Find executable in PATH directories. Returns full path if found, None otherwise."""
    executables = []
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for directory in path_dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for file in os.listdir(directory):
            full_path = os.path.join(directory, file)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                executables.append(file)
    return executables


def longest_common_prefix(matches):
    result = ""
    index = 0
    min_length = min([len(text) for text in matches])
    # print(matches)
    while index < min_length:
        if len(set([text[index] for text in matches])) > 1:
            return result
        index += 1
        result += matches[0][index]
    return result


def completer(text, state):
    global last_tab_count, last_tab_matches, last_tab_text

    built_in_functions = list(
        set(["exit", "echo", "type", "pwd", "history"] + find_all_executables())
    )
    matches = sorted([cmd for cmd in built_in_functions if cmd.startswith(text)])

    if text != last_tab_text:
        last_tab_text = text
        last_tab_count = 0

    # First tab: complete to longest common prefix if possible
    # prefix = longest_common_prefix(matches)
    # print(f"Here is the prefix: {prefix}")

    if state == 0 and len(matches) > 1:
        if last_tab_count == 0:
            if all(match.startswith(matches[0]) for match in matches[1:]):
                return matches[0]
            last_tab_count += 1
            sys.stdout.write("\a")
            return None
        else:
            print()
            print("  ".join(matches))
            sys.stdout.write(f"$ {text}")
            sys.stdout.flush()
            return text

    if state < len(matches):
        return matches[0] + " "


def run_external_program(command, args):

    executable_path = find_executable(command)
    result = subprocess.run([command] + args, executable=executable_path)


def change_dir(args):
    try:
        if args[0] == "~":
            os.chdir(os.environ.get("HOME", ""))
        else:
            os.chdir(args[0])
    except:
        print(f"cd: {args[0]}: No such file or directory")
    return


def echo_command(args):
    try:
        print(" ".join(args))

        return 1
    except:
        return 0


def history_command(args, history_stack):
    if "-r" in args:
        try:
            # print(args[1])
            with open(args[1], "r", encoding="utf-8") as f:
                for i, line in enumerate(f.readlines()):
                    history_stack.append(line.strip())
        except FileNotFoundError:
            print("Could not find file")
    elif "-w" in args:
        try:
            with open(args[1], "w") as f:
                for line in history_stack:
                    f.write(line + "\n")
        except:
            print("Something went wrong in writing into file")
    else:
        starting_index = 0
        if len(args) > 0:
            try:
                starting_index = len(history_stack) - int(args[0])
            except:
                print("Invalid args")
        for i in range(starting_index, len(history_stack)):
            print(f"\t{i}  {history_stack[i]}")


def main():
    history_stack = []
    while True:
        # sys.stdout.write("$ ")
        curr_input = input("$ ").strip()
        if not curr_input:
            continue

        if curr_input != "":
            history_stack.append(curr_input)
            readline.add_history(curr_input)

        temp = shlex.split(curr_input)
        command, args = temp[0], temp[1:]

        built_in_functions = ["exit", "echo", "type", "pwd", "history"]

        if "|" in curr_input:
            subprocess.call(curr_input, shell=True)
            # commands = [cmd.strip() for cmd in curr_input.split('|')]
            # execute_pipeline(commands)
        elif command == "history":
            history_command(args, history_stack)

        elif command == "exit":
            try:
                return int(args[0])
            except:
                print("unknown status")
        elif ">" in curr_input or "1>" in curr_input:
            os.system(curr_input)
        elif command == "echo":
            try:
                echo_command(args)
            except:
                print("")
        elif command == "type":
            if args[0] in built_in_functions:
                print(f"{args[0]} is a shell builtin")
            elif (full_path := find_executable(args[0])) is not None:
                print(f"{args[0]} is {full_path}")
            else:
                print(f"{args[0]}: not found")

        elif command == "pwd":
            print(os.getcwd())
        elif command == "cd":
            change_dir(args)
        elif find_executable(command):
            run_external_program(command, args)
        else:
            # attempt executable
            try:
                run_external_program(command, args)
            except:
                print(f"{command}: command not found")


if __name__ == "__main__":

    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)
    # attempt to set the auto history to false because it doesn't work on Windows for some reason
    try:
        readline.set_auto_history(False)
    except:
        pass
    main()