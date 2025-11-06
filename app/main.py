import sys

def main():
    while True:
        try:
            # Show shell prompt
            sys.stdout.write("$ ")
            sys.stdout.flush()

            # Read user input
            line = input()
        except EOFError:
            # Handle Ctrl+D gracefully
            print()
            break
        except KeyboardInterrupt:
            # Handle Ctrl+C — show new line and prompt again
            print()
            continue

        # Remove leading/trailing spaces
        line = line.strip()

        # Empty input → show prompt again
        if not line:
            continue

        # Split into tokens (command + arguments)
        tokens = line.split()
        command = tokens[0]

        # --- Handle 'exit' builtin ---
        if command == "exit":
            # Default exit code = 0
            exit_code = 0

            # If user provided an argument (like 'exit 1')
            if len(tokens) > 1:
                try:
                    exit_code = int(tokens[1])
                except ValueError:
                    # Invalid argument (non-numeric)
                    print(f"exit: {tokens[1]}: numeric argument required")
                    exit_code = 1  # Standard shell behavior

            # Terminate shell immediately
            sys.exit(exit_code)

        # --- Handle all other invalid commands ---
        print(f"{command}: command not found")

if __name__ == "__main__":
    main()
