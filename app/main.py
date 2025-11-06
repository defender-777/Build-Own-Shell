import sys

def main():
    while True:
        try:
            # Show prompt
            sys.stdout.write("$ ")
            sys.stdout.flush()

            # Read user input
            line = input()
        except EOFError:
            print()  # Handle Ctrl+D
            break
        except KeyboardInterrupt:
            print()  # Handle Ctrl+C
            continue

        # Clean up input
        line = line.strip()

        # Skip empty input
        if not line:
            continue

        # Split input into command + args
        tokens = line.split()
        command = tokens[0]
        args = tokens[1:]  # all words after command

        # --- Handle 'exit' builtin ---
        if command == "exit":
            exit_code = 0
            if len(args) > 0:
                try:
                    exit_code = int(args[0])
                except ValueError:
                    print(f"exit: {args[0]}: numeric argument required")
                    exit_code = 1
            sys.exit(exit_code)

        # --- Handle 'echo' builtin ---
        elif command == "echo":
            # Join arguments with spaces and print
            print(" ".join(args))

        # --- Handle invalid commands ---
        else:
            print(f"{command}: command not found")

if __name__ == "__main__":
    main()
