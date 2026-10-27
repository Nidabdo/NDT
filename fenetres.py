"""Placement commun des fenêtres sur le moniteur de l'application."""
import ctypes
from ctypes import wintypes
import tkinter as tk


def position_centree(zone, largeur, hauteur):
    gauche, haut, droite, bas = zone
    return (gauche + max(0, (droite-gauche-largeur)//2),
            haut + max(0, (bas-haut-hauteur)//2))


def centrer_fenetre(win):
    if getattr(win, '_centrage_en_cours', False):return
    win._centrage_en_cours=True
    try:
        win.update_idletasks()
        app=win._root()
        user32=ctypes.WinDLL('user32',use_last_error=True)
        user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        user32.GetAncestor.restype=wintypes.HWND
        user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
        user32.MonitorFromWindow.restype=wintypes.HANDLE
        class MonitorInfo(ctypes.Structure):
            _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
                      ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]
        user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)]
        user32.GetMonitorInfoW.restype=wintypes.BOOL
        user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype=wintypes.BOOL
        user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                                      ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user32.SetWindowPos.restype=wintypes.BOOL
        owner=user32.GetAncestor(app.winfo_id(),2)
        hwnd=user32.GetAncestor(win.winfo_id(),2)
        monitor=user32.MonitorFromWindow(owner,2)  # écran contenant la plus grande partie de NDT
        info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
        rect=wintypes.RECT()
        if not user32.GetMonitorInfoW(monitor,ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
        if not user32.GetWindowRect(hwnd,ctypes.byref(rect)):raise ctypes.WinError(ctypes.get_last_error())
        zone=info.rcWork  # exclut la barre des tâches
        x,y=position_centree((zone.left,zone.top,zone.right,zone.bottom),rect.right-rect.left,rect.bottom-rect.top)
        if not user32.SetWindowPos(hwnd,None,x,y,0,0,0x0001|0x0004|0x0010):raise ctypes.WinError(ctypes.get_last_error())
    except (AttributeError,OSError):
        x,y=position_centree((0,0,win.winfo_screenwidth(),win.winfo_screenheight()),win.winfo_width(),win.winfo_height())
        win.geometry(f'+{x}+{y}')
    finally:
        win._centrage_en_cours=False


class Popup(tk.Toplevel):
    """Centre une seule fois, après calcul de la taille ; reste ensuite déplaçable."""
    def __init__(self,master=None,**kwargs):
        super().__init__(master,**kwargs)
        self._placement_initial=False
        self.bind('<Map>',self._placer,add='+')

    def _placer(self,event):
        if event.widget==self and not self._placement_initial:
            self._placement_initial=True
            centrer_fenetre(self)
