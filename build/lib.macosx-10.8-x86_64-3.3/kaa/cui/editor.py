import itertools, curses, curses.panel
from kaa.cui.wnd import Window
import kaa
from kaa import LOG
from kaa import screen, cursor
from kaa.cui.color import ColorName

class TextEditorWindow(Window):
    """Text editor window"""

    splitter = None
    document = None
    keydispatcher = None
    statusbar = None

    def _oninit(self):
        super()._oninit()
        self._cwnd.leaveok(0)
        self._cwnd.scrollok(0)


        self.screen = screen.Screen()
        self.screen.setsize(*self.getsize())
        self.cursor = cursor.Cursor(self)
        self.pending_str = ''
        self._drawn_rows = {}


    def destroy(self):
        if self.document:
            self.document.del_window(self)
        self.screen.close()
        self.document = self.screen = self.cursor = None
        self.splitter = self.keydispatcher = None
        self.statusbar = None

        super().destroy()

    def show_doc(self, doc):
        if self.document:
            self.document.del_window(self)

        self._oninit()

        self.document = doc
        self.screen.set_document(doc)
        self.document.add_window(self)
        self.pending_str = ''

        self.keydispatcher = self.document.mode.create_keydispatcher()

        self._drawn_rows = {}
        self.draw_screen()
        self.refresh()

    def dup(self):
        ret = self.__class__(parent=self.parent)
        ret.show_doc(self.document)
        return ret

    def set_splitter(self, splitter):
        self.splitter = splitter

    def set_statusbar(self, statusbar):
        self.statusbar = statusbar

    def bring_top(self):
        self._update_activeframe()
        if curses.panel.top_panel() is not self._panel:
            super().bring_top()

            self.draw_screen(force=True)

    def set_cursor(self, cursor):
        self.cursor = cursor

    def _flush_pending_str(self):
        if self.pending_str:
            pending = self.pending_str
            self.pending_str = ''
            self.document.mode.on_str(self, pending)
            if not self.closed:
                self.update_window()
            return True

    def on_keyevent(self, event):
        s, commands, candidate = self.keydispatcher.on_key(
                                    event.key, self.document.mode.keybind)
        try:
            if s:
                self.pending_str += s
            elif commands:
                self._flush_pending_str()
                self.document.mode.on_commands(self, commands)
        finally:
            if s or commands or not candidate:
                if not self.closed:
                    self.keydispatcher.reset_keys()

        return

    def on_esc_pressed(self, event):
        self._flush_pending_str()
        self.document.mode.on_esc_pressed(self, event)

    def _update_activeframe(self):
        frame = self.get_label('frame')
        if frame:
            self.mainframe.activeframe = frame
            frame.set_active_editor(self)

    def on_focus(self):
        self._update_activeframe()

        if self.document:
            curses.curs_set(self.document.mode.get_cursor_visibility())
            # relocate cursor
            self.cursor.setpos(self.cursor.pos)

    def _getcharattrs(self, row):
        # returns character attributes of each characters in row.

        selrange = self.screen.selection.get_range()
        if selrange:
            selfrom, selto = selrange
        else:
            selfrom = selto = -1

        for pos in row.positions:
            attr = 0
            if selfrom <= pos < selto:
                attr = curses.A_REVERSE

            color = kaa.app.colors.get_color(
                ColorName.DEFAULT,
                ColorName.DEFAULT)

            tokenid = self.document.styles.getints(pos, pos+1)[0]

            if self.document.mode.highlight:
                style = self.document.mode.get_style(tokenid)
                color = style.cui_colorattr
                if style.underline:
                    color += curses.A_UNDERLINE
                if style.bold:
                    color += curses.A_BOLD

            yield (color + attr, style.rjust)

    def draw_screen(self, force=False):
        try:
            self._draw_screen(force=force)
        except curses.error:
            LOG.debug('error on drawing: {}'.format(self), exc_info=True)

    def _draw_screen(self, force=False):
        frame = self.get_label('frame')
        if frame:
            if self.mainframe.activeframe is not frame:
                return

        self.screen.apply_updates()
        if kaa.app.focus:
            cury, curx = kaa.app.focus._cwnd.getyx()

        h, w = self._cwnd.getmaxyx()

        rows = list(self.screen.get_visible_rows())
        cur_sel = self.screen.selection.get_range()

        theme = self.document.mode.theme
        color = theme.get_style('default').cui_colorattr

        if force:
            drawn = {}
            updated = True
        else:
            updated = len(rows) != len(self._drawn_rows)
            drawn = self._drawn_rows
        self._drawn_rows = {}
        for n, row in enumerate(rows):
            if n > h:
                break
            if drawn.get(row) == (n, cur_sel):
                # The raw was already drawn.
                continue

            updated = True
            s = 0

            # clear row
            self._cwnd.move(n, 0)
            self._cwnd.clrtoeol()
            self._cwnd.chgat(n, 0, -1, color)

            # move cursor to top of row
            self._cwnd.move(n, row.wrapindent)

            rjust = False
            for (attr, attr_rjust), group in itertools.groupby(self._getcharattrs(row)):
                if not rjust and attr_rjust:
                    rjust = True

                    rest = sum(row.cols[s:])
                    cy, cx = self._cwnd.getyx()
                    self._cwnd.move(cy, w-rest)

                slen = len(tuple(group))
                letters = ''.join(row.chars[s:s+slen]).rstrip('\n')
                self.add_str(letters, attr)
                s += slen

            self._drawn_rows[row] = (n, cur_sel)

        if len(rows) < h:
            self._cwnd.move(len(rows), 0)
            self._cwnd.clrtobot()

        if kaa.app.focus:
            kaa.app.focus._cwnd.move(cury, curx)

        return updated

    def on_document_updated(self, pos, inslen, dellen):
        self.screen.on_document_updated(pos, inslen, dellen)

    def style_updated(self, posfrom, posto):
        f, t = self.screen.get_visible_range()
        if posfrom <= t and f <= posto:
            self.screen.style_updated()
            updated = self.screen.apply_updates()
            if updated:
                self.draw_screen(force=True)
                self.refresh()

    CURSOR_TO_MIDDLE_ON_SCROLL = True
    def locate_cursor(self, pos):
        updated = self.screen.apply_updates()
        self.screen.locate(pos,
                           middle=self.CURSOR_TO_MIDDLE_ON_SCROLL,
                           bottom=not self.CURSOR_TO_MIDDLE_ON_SCROLL)

        idx, x = self.screen.getrowcol(pos)
        y = idx - self.screen.portfrom

        if (y, x) != self._cwnd.getyx():
            h, w = self._cwnd.getmaxyx()
            if y < h and x < w and y >=0 and x >= 0:
                self._cwnd.move(y, x)

        retpos = self.screen.get_pos_under(idx, x)
        self.document.mode.on_cursor_located(self, retpos, y, x)
        return retpos, y, x

    def linedown(self):
        if self.screen.linedown():
            self.draw_screen()
            self.refresh()
            return True

    def lineup(self):
        if self.screen.lineup():
            self.draw_screen()
            self.refresh()
            return True

    def pagedown(self):
        if self.screen.pagedown():
            self.draw_screen()
            self.refresh()
            return True

    def pageup(self):
        if self.screen.pageup():
            self.draw_screen()
            self.refresh()
            return True

    def on_setrect(self, l, t, r, b):
        self._drawn_rows = {}
        if self.document:
            w = max(2, r-l)
            h = max(1, b-t)
            self.screen.setsize(w, h)
            self.draw_screen()
            self.cursor.setpos(self.cursor.pos) # relocate cursor
            self.cursor.savecol()

            self.refresh()

    def update_window(self):

        # if this editor is a part of ChildFrame,
        # update if the ChildFrame is active.
        frame = self.get_label('frame')
        if frame:
            if self.mainframe.activeframe is not frame:
                return

        self.screen.apply_updates()
        if self.draw_screen():
            self.refresh()
            self.cursor.refresh()
            return True

    def on_killfocus(self):
        self._drawn_rows = {}
        self._flush_pending_str()

    def on_idle(self):
        if not self.closed:
            if self.pending_str:
                return self._flush_pending_str()

            return self.update_status()

    def update_status(self):
        if self.statusbar:
            modified = ''
            if self.document.undo:
                if self.document.undo.is_dirty():
                    modified = True

            updated = self.statusbar.set_info(
                filename=self.document.get_title(),
                modified_mark='*' if modified else '')

            return updated

