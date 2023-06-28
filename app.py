import os


from tools import helpers

path = os.path.dirname(os.path.abspath(__file__))

file = os.path.join(path, "data", "input.csv")

help_text = """List of Commands :

help      - displays this message.
exit      - exits the program.
states    - print a json file containing all states.
districts - print a json file containing all districts wrt states.
offices   - print a json file containing all offices wrt districts.
areas     - prints a json file containing all areas wrt offices.

"""

greeting = "Enter a command ( type help for details ): "


def command_processor(command):
    if command == "exit" or command == "q":
        print("Bye Bye! 👋")
        return False

    elif command == "states":
        helpers.get_states(file)

    elif command == "districts":
        helpers.get_districts(file)

    elif command == "areas":
        helpers.get_areas(file)

    elif command == "offices":
        helpers.get_offices(file)

    elif command == "help":
        helpers.clear_console()
        print(help_text)
    else:
        print("Unknown command. Please try again.")

    return True


if __name__ == "__main__":
    while True:
        user_input = input(greeting)

        if not command_processor(user_input):
            break
