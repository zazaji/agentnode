import platform
from .windows import WindowsAdapter
from .linux import LinuxAdapter
from .macos import MacAdapter
def get_platform_adapter():
    s=platform.system().lower()
    if s=="windows": return WindowsAdapter()
    if s=="darwin": return MacAdapter()
    return LinuxAdapter()
