


import inquirer


lazy_mode_with_menu = True
auto_confirm = True

built_in_menu = []


def start_actions():
    global built_in_menu
    built_in_menu = []


def confirm_action(action, function):


    if auto_confirm:
        print(f"Running: {action}")
        function()
        return
    if lazy_mode_with_menu:
            built_in_menu.append((action, function)) 
    else: 
        response = input(f"{action}? (y/anything): ").strip().lower()
        if response == 'y':
            function()

def finish_actions():
    global built_in_menu

    if built_in_menu:





        print("\n--- Menu ---")

        menu_choices = [(action, action) for action, _ in built_in_menu]

        main_question = [
                    inquirer.List(
                        'action',
                        message="Use Arrow Keys to select an option and press Enter",
                        choices=menu_choices, 
                        carousel=True,
                    )
                ]
        
        answer = inquirer.prompt(main_question)
        selected_action = answer['action']
        index = next(i for i, (action, _) in enumerate(built_in_menu) if action == selected_action)
        
        _, function = built_in_menu[index]
        function()

    built_in_menu = []



def choose_option(options, message, can_give_custom_text=False):
    choices = options.copy()
    if can_give_custom_text:
        choices.append("Custom")
    
    question = [
        inquirer.List(
            'option',
            message=message,
            choices=choices,
            carousel=True,
        )
    ]
    
    answer = inquirer.prompt(question)
    selected_option = answer['option']
    
    if selected_option == "Custom":
        custom_text = input("Enter: ")
        return custom_text
    else:
        return selected_option