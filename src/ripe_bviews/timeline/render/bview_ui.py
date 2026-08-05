
'''

def unconstrained_get_options(self):
    choices = self.question.choices
    
    for index, choice in enumerate(choices):
        selected = index == self._current_index
        
        # This mirrors the library's styling rules
        if selected:
            color = self.theme.List.selection_color
            symbol = self.theme.List.selection_cursor
        else:
            color = self.theme.List.unselected_color
            symbol = " "
            
        yield choice, symbol, color 

def set_unrestrained_options():
    ListRender.get_options = unconstrained_get_options
'''