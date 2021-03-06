import re
import kaa
from kaa import document
from kaa.ui.dialog import dialogmode
from kaa.theme import Theme, Style
from kaa.ui.dialog import dialogmode

MsgBoxTheme = Theme('default', [
    Style('default', 'default', 'Magenta'),
    Style('underline', 'default', 'Magenta', underline=True),
    Style('caption', 'red', 'Green'),
    Style('button', 'default', 'magenta', nowrap=True),
    Style('button.shortcut', 'green', 'magenta', underline=True,
          bold=True, nowrap=True),
])

class MsgBoxMode(dialogmode.DialogMode):
    SEPARATOR = '/'
    def init_theme(self):
        self.theme = MsgBoxTheme

    def init_keybind(self):
        pass

    def init_commands(self):
        pass # no commands

    def on_str(self, wnd, s):
        pass

    def build_document(self):
        pass

    def on_start(self, wnd):
        wnd.cursor.setpos(self.document.endpos()-1)

    def on_str(self, wnd, s):
        for c in s:
            c = c.lower()
            if c in self.shortcuts:
                self.on_shortcut(wnd, c)
                return
            if self.keys and (c in self.keys):
                self.on_shortcut(wnd, c)
                return

    def on_shortcut(self, wnd, c):
        # Destroy popup window
        popup = wnd.get_label('popup')
        if popup:
            popup.destroy()

        # return value
        if c:
            c = c.lower()
        self._runcallback(c)

    def _runcallback(self, c):
        self.callback(c)

    def on_esc_pressed(self, wnd, event):
        self.on_shortcut(wnd, None)

    def _show_window(self):
        kaa.app.show_dialog(self.document)

    @classmethod
    def build_msgbox(cls, caption, options, callback, keys=None):
        buf = document.Buffer()
        doc = document.Document(buf)
        mode = cls()
        mode.callback = callback
        mode.keys  = keys
        doc.setmode(mode)

        f = dialogmode.FormBuilder(doc)

        # caption
        if caption:
            f.append_text('caption', caption)
            f.append_text('default', ' ')

        mode.shortcuts = {}
        for n, option in enumerate(options):
            m = re.search(r'&([^&])', option)
            shortcut = m.group(1)
            mode.shortcuts[shortcut.lower()] = option

            f.append_text('button',
                          option,
                          on_shortcut=
                            lambda wnd, key=shortcut:mode.on_shortcut(wnd, key),
                          shortcut_style='button.shortcut')

            if n < len(options)-1:
                f.append_text('default', cls.SEPARATOR)

        f.append_text('default', ' ')
        f.append_text('underline', ' ')

        return doc

    @classmethod
    def show_msgbox(cls, caption, options, callback, keys=None):
        doc = cls.build_msgbox(caption, options, callback, keys)
        doc.mode._show_window()
        return doc
