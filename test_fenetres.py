import tkinter as tk
import unittest
from unittest.mock import patch
from fenetres import Popup, position_centree


class PopupTest(unittest.TestCase):
    def test_monitor_coordinates(self):
        self.assertEqual(position_centree((0,0,1920,1040),820,740),(550,150))
        self.assertEqual(position_centree((-1920,0,0,1040),820,740),(-1370,150))
        self.assertEqual(position_centree((1920,-1080,3840,-40),820,740),(2470,-930))
        self.assertEqual(position_centree((-1280,0,0,680),1400,800),(-1280,0))

    def test_nested_dialogs_center_only_on_open(self):
        app=tk.Tk();self.addCleanup(app.destroy)
        app.update()
        with patch('fenetres.centrer_fenetre') as center:
            parent=Popup(app);parent.geometry('500x400');parent.update()
            child=Popup(parent);child.geometry('300x200');child.update()
            self.assertEqual([call.args[0] for call in center.call_args_list],[parent,child])
            parent.geometry('+100+100');parent.update()
            child.withdraw();child.deiconify();child.update()
            self.assertEqual(center.call_count,2)
            self.assertIs(child._root(),app)


if __name__=='__main__':unittest.main()
