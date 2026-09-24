from __future__ import annotations
import ctypes, platform, time
from ctypes import wintypes
from ..models import DesktopAct

class InputController:
    def act(self,a:DesktopAct):
        if platform.system()=='Windows': return self._win(a)
        try:
            import pyautogui
            return self._pyauto(a,pyautogui)
        except Exception as e:return {'ok':False,'error':str(e)}
    def _send_mouse(self,flags,data=0):
        ULONG_PTR=getattr(wintypes,'ULONG_PTR',ctypes.c_size_t)
        class MOUSEINPUT(ctypes.Structure): _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('mouseData',wintypes.DWORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ULONG_PTR)]
        class INPUT(ctypes.Structure): _fields_=[('type',wintypes.DWORD),('mi',MOUSEINPUT)]
        i=INPUT(0,MOUSEINPUT(0,0,data,flags,0,0)); return ctypes.windll.user32.SendInput(1,ctypes.byref(i),ctypes.sizeof(INPUT))==1
    def _unicode_text(self,text):
        ULONG_PTR=getattr(wintypes,'ULONG_PTR',ctypes.c_size_t)
        class KEYBDINPUT(ctypes.Structure): _fields_=[('wVk',wintypes.WORD),('wScan',wintypes.WORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ULONG_PTR)]
        class INPUT(ctypes.Structure): _fields_=[('type',wintypes.DWORD),('ki',KEYBDINPUT)]
        u=ctypes.windll.user32
        for ch in text:
            code=ord(ch)
            for flags in (0x0004,0x0004|0x0002):
                i=INPUT(1,KEYBDINPUT(0,code,flags,0,0)); u.SendInput(1,ctypes.byref(i),ctypes.sizeof(INPUT))
    def _win(self,a):
        try:
            u=ctypes.windll.user32
            if a.action in {'click','double_click','right_click','move'}:
                u.SetCursorPos(int(a.x or 0),int(a.y or 0))
                if a.action!='move':
                    right=a.action=='right_click'; down=0x0008 if right else 0x0002; up=0x0010 if right else 0x0004
                    for _ in range(2 if a.action=='double_click' else 1): self._send_mouse(down); self._send_mouse(up)
                return {'ok':True,'backend':'winapi-sendinput'}
            if a.action=='scroll': self._send_mouse(0x0800,int(a.amount*120)); return {'ok':True,'backend':'winapi-sendinput'}
            if a.action=='type_text': self._unicode_text(a.text or ''); return {'ok':True,'backend':'winapi-sendinput'}
            import pyautogui; return self._pyauto(a,pyautogui)
        except Exception as e:return {'ok':False,'error':str(e)}
    def _pyauto(self,a,p):
        if a.action=='scroll':p.scroll(a.amount)
        elif a.action=='type_text':p.write(a.text or '')
        elif a.action=='hotkey':p.hotkey(*(a.keys or []))
        return {'ok':True,'backend':'pyautogui'}
