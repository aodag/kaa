import itertools, re
from unicodedata import east_asian_width

from kaa import LOG
from kaa import document
from kaa.document import is_combine

class Row:
    height = 1
    bgcolor = None
    def __init__(self, posfrom, tol, wrapindent, chars, cols, 
            positions, intervals):
        self.posfrom = posfrom
        self.posto = positions[-1]+1 if positions else posfrom
        self.tol = tol
        self.wrapindent = wrapindent
        self.chars = chars
        self.cols = cols
        self.positions = positions
        self.intervals = intervals

    def get_char(self, pos):
        ret = []
        for p, c in zip(self.positions, self.chars):
            if p == pos:
                ret.append(c)
        return ''.join(ret)

TABWIDTH = 4



def translate_chars(posfrom, chars):
    """Build character informations from chars.

    Returns tuple of four lists. The first is a list of characters to be
    displayed. Second is a list of columns of each characters. Third is a 
    list of position in document of each characters.
    """

    curcol = 0
    dispchrs = ''
    dispcols = []
    positions = []
    intervals = []

    pos = posfrom
#    return chars, [1]*len(chars), [(posfrom+i) for i in range(len(chars))], [0]*len(chars)

    for c in chars:
        if c == '\t':
            dispstr = ' ' * (TABWIDTH - (curcol % TABWIDTH))
        elif (((c != '\n') and (c < '\x20')) # control chars
              or (c == '\x7f')                     # backspace
              or ('\ud800' <= c <= '\udfff')):     # surrogate pair
            dispstr = repr(c)[1:-1]
        else:
            dispstr = c

        dispchrs += dispstr
        for i, d in enumerate(dispstr):
            positions.append(pos)
            intervals.append(i)
            if curcol and is_combine(c):  # first char if line never be combined
                cols = 0
            else:
                cols = 2 if east_asian_width(d) in {'W', 'F', 'A'} else 1
            dispcols.append(cols)
            curcol += cols
        pos += 1

#    return chars, [1]*len(chars), [(posfrom+i) for i in range(len(chars))], [0]*len(chars)
    return dispchrs, dispcols, positions, intervals


MIN_WRAPCOLS = 10

def col_splitter(maxcol, tol, dispchrs, dispcols, positions, intervals, styles, stylemap, nowrap=False):
    """Split string by column"""

    if nowrap:
        return [Row(tol, tol, 0, dispchrs, dispcols, positions, intervals)]

    assert maxcol >= 2
    rowfrom = rowto = 0
    sumcols = 0
    wrappos = None
    sumcols_at_wrappos = 0

    posfrom = tol
    wrapindent = 0

    ret = []

    for col in dispcols:

        if not col:
            rowto += 1
            continue

        # check if nowrap
        if rowfrom < rowto:
            wrappable = True

            if rowto < len(positions):

                curpos = positions[rowto-1]
                nextpos = positions[rowto]

                tokenid = styles[curpos-tol]
                nexttokenid = styles[nextpos-tol]

                style = stylemap.get(tokenid, None)
                if style and style.nowrap:
                    nextstyle = stylemap.get(nexttokenid)
                    if nextstyle and nextstyle.nowrap:
                        wrappable = False

            if wrappable:
                wrappos = rowto
                sumcols_at_wrappos = sumcols

        if ((sumcols + col) >= (maxcol - wrapindent)) and (rowfrom != rowto):
            # do not split at newlines
            if (rowto >= len(dispchrs)) or (dispchrs[rowto] != '\n'):

                if wrappos is None:
                    # No wrappable position found. So, fill as many chars as we can.
                    wrappos = rowto
                    sumcols_at_wrappos = sumcols

                assert rowfrom != wrappos
                row = Row(posfrom, tol, wrapindent, dispchrs[rowfrom:wrappos],
                        dispcols[rowfrom:wrappos], positions[rowfrom:wrappos],
                        intervals[rowfrom:wrappos])

                ret.append(row)

                rowfrom = wrappos
                sumcols = sumcols - sumcols_at_wrappos

                wrappos = None
                sumcols_at_wrappos = None

                posfrom = row.posto

                # set wrap-indent width after second row
                if len(ret) == 1:
                    wrapindent = re.match(r' *', dispchrs).end()
                    if wrapindent + MIN_WRAPCOLS > maxcol:
                        wrapindent = max(0, maxcol-MIN_WRAPCOLS)

        sumcols += col
        rowto += 1

    if rowfrom != len(dispcols) or not dispchrs:
        row = Row(posfrom, tol, wrapindent, dispchrs[rowfrom:], dispcols[rowfrom:],
                positions[rowfrom:], intervals[rowfrom:])
        ret.append(row)

    return ret


class Selection:
    def __init__(self, screen):
        self._marks = document.Marks()
        self.screen = screen

    @property
    def start(self):
        return self._marks.get('start', None)

    @start.setter
    def start(self, pos):
        self._marks['start'] = pos

    @property
    def end(self):
        return self._marks.get('end', None)

    @end.setter
    def end(self, pos):
        self._marks['end'] = pos

    def clear(self):
        """Clear selection"""
        changed = self.is_started()
        self.start = self.end = None

        if changed:
            self.screen.style_updated()

    def is_started(self):
        """Return True if range was selected"""

        return self.start is not None

    def start_selection(self, pos):
        """Start range selection if it was not started"""

        if not self.is_started():
            self.start = self.end = pos

    def set_end(self, pos):
        """Update where selection ends."""

        assert self.is_started()

        changed = self.end != pos
        self.end = pos

        if changed:
            self.screen.style_updated()

    def get_range(self):
        if self.start is None or self.end is None:
            return None
        return tuple(sorted((self.start, self.end)))

    def set_range(self, f, t):
        if (self.start, self.end) != (f, t):
            self.start = f
            self.end = t
            self.screen.style_updated()

    def on_document_updated(self, pos, inslen, dellen):
        self._marks.updated(pos, inslen, dellen)


class Screen:
    """
    Attributes:
        rows --  list of Row objects.

        portfrom, portto -- Index of portion of rows to be displayed
            on the screen.
    """

    def __init__(self):
        self._oninit()
        self.width = 2      # width of screen
        self.height = 1     # height of screen

    def _oninit(self):
        self.document = None
        self.nowrap = False
        self.build_entire_rows = False

        # Rows displayed on screen
        # A row at self.rows[0] should be start from top
        # of document or from top of physical line.
        # A row at self.rows[-1] should be finished at end
        # of document or end of physical line.
        # An entire physical line will be stored in self.rows,
        # never be a part of physical line.
        self.rows = []
        self.portfrom = 0   # self.rows[self.portfrom:self.portto]
                            # returns rows displayed on the screen.
        self.portto = 0
        self.pos = 0        # Position of top-left corner
        self.updated_pos = None
        self._style_updated = False

        self.selection = Selection(self)



    def set_document(self, doc):
        self._oninit()

        self.document = doc
        self.nowrap = doc.mode.SCREEN_NOWRAP
        self.build_entire_rows = doc.mode.SCREEN_BUILD_ENTIRE_ROW

    def close(self):
        self.document = self.selection = None

    def get_visible_rows(self):
        return self.rows[self.portfrom:self.portto]

    def get_visible_range(self):
        rows = self.get_visible_rows()
        return (rows[0].posfrom, rows[-1].posto)

    def get_total_height(self):
        self.apply_updates()
        return sum(r.height for r in self.rows)

    def setsize(self, width, height):
        if self.width != width or self.height != height:
            self.width = max(2, width)
            self.height = max(1, height)
            if self.document:
                self.locate(self.pos, top=True, refresh=True)

    def _buildrow(self, pos, s, styles):
        dispchrs, dispcols, positions, intervals = translate_chars(pos, s)
        return col_splitter(self.width, pos, dispchrs, dispcols, 
                positions, intervals, styles, self.document.mode.stylemap, nowrap=self.nowrap)

    def _set_rowport(self):

        # Update bottom of visible rows
        height = 0
        for i in range(self.portfrom, len(self.rows)):
            if height >= self.height:
                self.portto = i
                break
            height += self.rows[i].height
        else:
            self.portto = len(self.rows)

        # Remove unnecessary rows
        if not self.build_entire_rows:
            porttop = self.rows[self.portfrom].tol
            for i, row in enumerate(self.rows):
                if row.tol == porttop:
                    del self.rows[0:i]
                    self.portfrom -= i
                    self.portto -= i
                    break

            portend = self.rows[self.portto-1].tol
            for i, row in enumerate(self.rows[self.portto:]):
                if row.tol != portend:
                    del self.rows[self.portto+i:]
                    break

    def on_document_updated(self, pos, inslen, dellen):
        self.selection.on_document_updated(pos, inslen, dellen)

        if not self.rows:
            return

        # calculate new top of screen position after update
        if pos > self.rows[-1].posto:
            # Nothing changed on screen
            return

        if self.updated_pos is None:
            self.updated_pos = self.rows[self.portfrom].posfrom

        if inslen >= dellen:
            if pos < self.updated_pos:
                self.updated_pos += inslen - dellen
        elif inslen < dellen:
            deleted = dellen - inslen
            if pos < self.updated_pos:
                if pos + deleted > self.updated_pos:
                    self.updated_pos = pos
                else:
                    tol = self.document.gettol(self.updated_pos - deleted) 
                    if tol != self.document.gettol(pos):
                        # Position of top of screen is not changed 
                        # if deleted on same physical line.
                        self.updated_pos -= deleted

        self.updated_pos = min(self.updated_pos, self.document.endpos())

    def style_updated(self):
        self._style_updated = True

    def apply_updates(self):
        if not self.rows:
            self.locate(0, top=True)
            return True
        ret = self._style_updated
        self._style_updated = False

        if self.updated_pos is not None:
            ret = self.locate(self.updated_pos,
                        top=True, refresh=True) or ret
        self.updated_pos = None
        return ret

    def is_lastrow(self, row):
        if row.posto == self.document.endpos():
            if not row.chars:
                return True
            if not row.chars[-1].endswith('\n'):
                return True

    def is_visible(self, pos):
        idx, col = self.getrowcol(pos)
        if idx == -1:
            return False
        return self.portfrom <= idx < self.portto

    def get_pos_under(self, rowidx, col):
        """Get pos at col of row when cursor downed from above row"""

        row = self.rows[rowidx]
        pos = self._getpos_fromrowcol(row, col)

        # Return next pos if the pos start at a row above
        if row.cols:
            if (row.positions[0] == pos) and (row.intervals[0] != 0):
                pos = self.document.get_nextpos(pos)

        return pos

    def get_pos_above(self, rowidx, col):
        """Get pos at col of row when cursor upped from below row"""

        row = self.rows[rowidx]
        pos = self._getpos_fromrowcol(row, col)

        # Return next pos if the pos start at a row above
        if row.cols:
            if (row.positions[0] == pos) and (row.intervals[0] != 0):
                nextpos = self.document.get_nextpos(pos)
                if nextpos < row.positions[-1]:
                    return nextpos

        return pos

    def _getpos_fromrowcol(self, row, col):
        """Returns position of specified column"""

        if not row.cols:
            return row.posfrom

        p = 0
        col = col - row.wrapindent
        for pos, charcols, c, i in zip(row.positions, row.cols,
                                       row.chars, row.intervals):
            if (p + charcols > col) or (c == '\n'):
                return pos
            p += charcols
        else:
            if self.is_lastrow(row):
                return row.posto
            else:
                ret = row.positions[-1]
                return ret

    def getrow(self, pos):
        assert pos is not None
        if self.rows and self.rows[0].posfrom <= pos:
            for i, row in enumerate(self.rows):
                if row.posfrom <= pos < row.posto:
                    return i, row
            if self.rows and self.is_lastrow(self.rows[-1]):
                return len(self.rows)-1, self.rows[-1]

        return -1, None

    def getrowcol(self, pos):
        idx, row = self.getrow(pos)
        if idx == -1:
            return -1, -1
        else:
            try:
                col = row.positions.index(pos)
            except ValueError:
                col = len(row.positions)
            return idx, sum(c for c in row.cols[:col])+row.wrapindent

    def _fillscreen(self):
        while True:
            bottomrow = self.rows[-1]
            if self.is_lastrow(bottomrow):
                break

            height = sum(row.height for row in self.rows[self.portfrom:])
            if not self.build_entire_rows and (height >= self.height):
                break

            eol, s = self.document.getline(bottomrow.posto)
            styles = self.document.get_styles(bottomrow.posto, eol)
            self.rows.extend(self._buildrow(bottomrow.posto, s, styles))
       
        self._set_rowport()

    def locate(self, pos, top=False, middle=False, bottom=False,
               align_always=False, refresh=False):

        assert top or middle or bottom
        if self.updated_pos is not None:
            refresh = True
            self.updated_pos = None

        self._style_updated = False

        posidx = -1
        if not refresh:
            posidx, posrow = self.getrow(pos)

        if not refresh and (posidx != -1):
            if not align_always and (self.portfrom <= posidx < self.portto):
                return False
        elif self.build_entire_rows:
            eol, s = self.document.getline(0)
            styles = self.document.get_styles(0, eol)
            self.rows = self._buildrow(0, s, styles)
            self._fillscreen()
            posidx, posrow = self.getrow(pos)
        else:
            # build specified row
            tol = self.document.gettol(pos)
            eol, s = self.document.getline(tol)
            styles = self.document.get_styles(tol, eol)
            self.rows = self._buildrow(tol, s, styles)
            posidx, posrow = self.getrow(pos)

        self.vert_align(posidx, top, middle, bottom)
        return True

    def vert_align(self, rowidx, top=False, middle=False, bottom=False):
        assert top or middle or bottom
        # move the row to middle or bottom

        targetrow = self.rows[rowidx]

        if top:
            rowbottom = 0
        elif middle:
            rowbottom = self.height // 2
        else:
            # bottom
            rowbottom = max(0, self.height - targetrow.height)

        if rowbottom > 0:
            # build rows above target row
            height = sum(row.height for row in self.rows[:rowidx+1])

            while height <= rowbottom:
                curtop = self.rows[0].posfrom
                if curtop == 0:
                    # top of buffer
                    break

                # build previous line
                top = self.document.gettol(curtop-1)
                eol, s = self.document.getline(top)
                styles = self.document.get_styles(top, eol)
                rows = self._buildrow(top, s, styles)
                height += sum(row.height for row in rows)
                rowidx += len(rows)

                self.rows[0:0] = rows

            # move row
            height = 0
            for n in range(rowidx, -1, -1):
                if height > rowbottom:
                    break
                row = self.rows[n]
                height += row.height
                rowidx = n

        self.portfrom = rowidx
        self.pos = self.rows[rowidx].posfrom

        self._fillscreen()

    def linedown(self):
        if self.portfrom < len(self.rows) - 1:
            self.portfrom += 1
            self.pos = self.rows[self.portfrom].posfrom
            self._fillscreen()
            return True
        else:
            currow = self.rows[self.portfrom]
            if not self.is_lastrow(currow):
                self.locate(currow.posto, top=True)
                return True
        return False

    def lineup(self):
        if self.portfrom > 0:
            self.portfrom -= 1
            self.pos = self.rows[self.portfrom].posfrom
            self._fillscreen()
            return True

        elif self.pos > 0:
            tol = self.document.gettol(self.pos-1)
            eol, s = self.document.getline(tol)
            styles = self.document.get_styles(tol, eol)
            rows = self._buildrow(tol, s, styles)
            self.rows[0:0] = rows
            self.pos = rows[-1].posfrom
            self.portfrom = len(rows)-1
            self._fillscreen()
            return True

        return False

    def pagedown(self):
        if self.height != 1:
            curpos = self.pos
            self.vert_align(self.portto-1, top=True)
            return self.pos != curpos
        else:
            return self.linedown()


    def pageup(self):
        if self.height != 1:
            curpos = self.pos
            self.vert_align(self.portfrom, bottom=True)
            return self.pos != curpos
        else:
            return self.lineup()
