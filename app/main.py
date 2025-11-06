import sys

# Keep a set of builtins for easy lookup
BUILTINS = {"exit", "echo", "type"}

def main():
    while True:
        try:
            # --- Prompt & Input ---
            sys.stdout.write("$ ")
            sys.stdout.flush()
            line = input()
        except EOFError:
            print()      # Handle Ctrl+D
            break
        except KeyboardInterrupt:
            print()      # Handle Ctrl+C
            continue

        # --- Parse Input ---
        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        command = tokens[0]
        args = tokens[1:]

        # --- exit builtin ---
        if command == "exit":
            exit_code = 0
            if args:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # --- echo builtin ---
        elif command == "echo":
            print(" ".join(args))

        # --- type builtin ---
        elif command == "type":
            # Must have an argument: type <something>
            if not args:
                print("type: missing argument")
                continue

            target = args[0]
            if target in BUILTINS:
                print(f"{target} is a shell builtin")
            else:
                print(f"{target}: not found")

        # --- Unknown command ---
        else:
            print(f"{command}: command not found")

if __name__ == "__main__":
    main()
