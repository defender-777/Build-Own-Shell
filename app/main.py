import sys

def main():
    """
    REPL for Stage 3:
    - Show prompt "$ "
    - Read a line
    - If empty: show prompt again
    - If command is 'exit' or 'quit': exit
    - Otherwise print "<command_name>: command not found"
    - Handle Ctrl-C (KeyboardInterrupt) by showing a fresh prompt
    - Handle Ctrl-D (EOFError) by exiting cleanly
    """
    while True:
        try:
            # Read: show prompt and flush so it appears immediately
            sys.stdout.write("$ ")
            sys.stdout.flush()

            # Wait for user input (blocking)
            line = input()
        except EOFError:
            # Ctrl-D (end-of-file) — exit the REPL politely with a newline
            print()
            break
        except KeyboardInterrupt:
            # Ctrl-C — don't exit the shell; print a newline and show prompt again
            print()
            continue

        # Trim whitespace
        line = line.strip()

        # If the user pressed Enter on an empty line, just loop and show prompt again
        if not line:
            continue

        # Allow explicit exits
        if line in ("exit", "quit"):
            break

        # Eval/Print: for this stage treat all commands as invalid.
        # Print the command *name* (first token) as required by tests.
        command_name = line.split()[0]
        print(f"{command_name}: command not found")

if __name__ == "__main__":
    main()
