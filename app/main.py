import sys
import os

# Builtin commands recognized by our shell
BUILTINS = {"exit", "echo", "type"}

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

        # --- Handle 'exit' ---
        if command == "exit":
            exit_code = 0
            if args:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # --- Handle 'echo' ---
        elif command == "echo":
            print(" ".join(args))

        # --- Handle 'type' ---
        elif command == "type":
            if not args:
                print("type: missing argument")
                continue

            target = args[0]

            # Case 1: Builtin command
            if target in BUILTINS:
                print(f"{target} is a shell builtin")
                continue

            # Case 2: Search for executable in PATH
            found = False
            for directory in os.environ["PATH"].split(":"):
                full_path = os.path.join(directory, target)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    print(f"{target} is {full_path}")
                    found = True
                    break

            # Case 3: Not found
            if not found:
                print(f"{target}: not found")

        # --- Handle unknown commands ---
        else:
            print(f"{command}: command not found")

if __name__ == "__main__":
    main()
