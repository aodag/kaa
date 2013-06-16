from unittest.mock import patch
from kaa.ui.msgbox import msgboxmode
import kaa_testutils

class TestSearchDlgMode(kaa_testutils._TestDocBase):

    @patch('kaa.app', create=True)
    def test_msbbox(self, mock):

        def cb(c):
            pass
        doc = msgboxmode.MsgBoxMode.show_msgbox(
            'caption', ['&Yes', '&No', '&All', '&Cancel'], cb)

        assert doc.mode.shortcuts == {
            'y':'&Yes', 'n':'&No', 'a':'&All', 'c':'&Cancel'
    }