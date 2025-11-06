import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    sys.stdout.write("$ ")
    #sys.stdout.flush() #Ensure the "$" appears before input 

    #Read user command from input 
    command = input()

    #Print the 'command not found' message
    print(f"{command}: command not found")





if __name__ == "__main__":
    main()
