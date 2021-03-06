from kaa.command import Commands, command
from kaa import document
from kaa.ui.dialog import dialogmode
from kaa.theme import Theme, Style
from kaa.keyboard import *

MoveSeparatorTheme = Theme('default', [
    Style('default', 'default', 'Blue'),
])

moveseparator_keys = {
    left: 'moveseparator.prev',
    right: 'moveseparator.next',
    '\n': 'moveseparator.close',
}

class MoveSeparatorCommands(Commands):
    @command('moveseparator.prev')
    def prev(self, wnd):
        if wnd.document.mode.target:
            wnd.document.mode.target.separator_prev()

    @command('moveseparator.next')
    def next(self, wnd):
        if wnd.document.mode.target:
            wnd.document.mode.target.separator_next()

    @command('moveseparator.close')
    def close(self, wnd):
        # restore cursor
        wnd.document.mode.org_wnd.activate()

        # Destroy popup window
        popup = wnd.get_label('popup')
        if popup:
            popup.destroy()
        wnd.document.mode.org_wnd.activate()

class MoveSeparatorMode(dialogmode.DialogMode):
    @classmethod
    def build(cls, target):
        buf = document.Buffer()
        doc = document.Document(buf)
        mode = cls()
        doc.setmode(mode)

        mode.org_wnd = target
        mode.target = target.splitter.parent

        f = dialogmode.FormBuilder(doc)
        f.append_text('default', 'Hit cursor left/right key to resize window.')
        return doc

    def init_keybind(self):
        self.keybind.add_keybind(moveseparator_keys)

    def init_commands(self):
        super().init_commands()

        self.moveseparator_commands = MoveSeparatorCommands()
        self.register_command(self.moveseparator_commands)

    def init_theme(self):
        self.theme = MoveSeparatorTheme

    def get_cursor_visibility(self):
        return 0   # hide cursor

    def on_esc_pressed(self, wnd, event):
        self.moveseparator_commands.close(wnd)

    def on_str(self, wnd, s):
        pass

def move_separator(wnd):
    doc = MoveSeparatorMode.build(wnd)
    kaa.app.show_dialog(doc)

