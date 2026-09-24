from __future__ import annotations
import ctypes, platform
from ctypes import wintypes

class WindowsNative:
    def __init__(self): self.available=platform.system()=='Windows'
    def windows(self):
        if not self.available:return []
        user32=ctypes.windll.user32; out=[]; EnumProc=ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
        @EnumProc
        def cb(hwnd,lparam):
            if not user32.IsWindowVisible(hwnd): return True
            n=user32.GetWindowTextLengthW(hwnd); buf=ctypes.create_unicode_buffer(n+1); user32.GetWindowTextW(hwnd,buf,n+1)
            if not buf.value.strip(): return True
            rect=wintypes.RECT(); user32.GetWindowRect(hwnd,ctypes.byref(rect)); pid=wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            out.append({'hwnd':int(hwnd),'title':buf.value,'pid':pid.value,'bounds':[rect.left,rect.top,rect.right,rect.bottom]}); return True
        user32.EnumWindows(cb,0); return out
    def control(self,hwnd:int,action:str,x:int|None=None,y:int|None=None,w:int|None=None,h:int|None=None):
        if not self.available:return {'available':False,'reason':'Windows only'}
        u=ctypes.windll.user32
        if action=='focus': ok=bool(u.SetForegroundWindow(hwnd))
        elif action=='minimize': ok=bool(u.ShowWindow(hwnd,6))
        elif action=='maximize': ok=bool(u.ShowWindow(hwnd,3))
        elif action=='restore': ok=bool(u.ShowWindow(hwnd,9))
        elif action=='close': ok=bool(u.PostMessageW(hwnd,0x0010,0,0))
        elif action=='move': ok=bool(u.SetWindowPos(hwnd,0,int(x or 0),int(y or 0),int(w or 800),int(h or 600),0x0004))
        elif action=='topmost': ok=bool(u.SetWindowPos(hwnd,-1,0,0,0,0,0x0001|0x0002))
        else: raise ValueError('unsupported window action')
        return {'ok':ok,'hwnd':hwnd,'action':action}
