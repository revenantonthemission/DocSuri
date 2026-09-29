"""Noninteractive, readonly macOS custom Keychain retrieval via Security.framework."""

import ctypes
import os
import stat
import sys
from pathlib import Path


class KeyUnavailable(PermissionError):
    pass


class KeychainReader:
    def __init__(self, path: Path):
        self.path = path

    def get(self, service: str, account: str) -> bytes:
        if sys.platform != "darwin":
            raise KeyUnavailable("macOS Keychain capability unavailable")
        info = self.path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid not in {0, os.getuid()}
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise KeyUnavailable("unsafe keychain owner or mode")
        security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        pointer = ctypes.c_void_p
        security.SecKeychainOpen.argtypes = [ctypes.c_char_p, ctypes.POINTER(pointer)]
        security.SecKeychainOpen.restype = ctypes.c_int32
        security.SecKeychainSetUserInteractionAllowed.argtypes = [ctypes.c_bool]
        security.SecKeychainSetUserInteractionAllowed.restype = ctypes.c_int32
        security.SecKeychainFindGenericPassword.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(pointer),
            ctypes.POINTER(pointer),
        ]
        security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        security.SecKeychainItemFreeContent.argtypes = [pointer, pointer]
        core.CFRelease.argtypes = [pointer]
        keychain, content, item = pointer(), pointer(), pointer()
        size = ctypes.c_uint32()
        if security.SecKeychainSetUserInteractionAllowed(False):
            raise KeyUnavailable("keychain interaction policy unavailable")
        if security.SecKeychainOpen(os.fsencode(self.path), ctypes.byref(keychain)):
            raise KeyUnavailable("custom keychain unavailable")
        try:
            s, a = service.encode(), account.encode()
            status = security.SecKeychainFindGenericPassword(
                keychain,
                len(s),
                s,
                len(a),
                a,
                ctypes.byref(size),
                ctypes.byref(content),
                ctypes.byref(item),
            )
            if status or not 0 < size.value <= 65_536:
                # A nonzero status is three different operator problems wearing one message: the
                # keychain is locked (-25308, interaction is disallowed because it is set off
                # above), the item is absent (-128), or the ACL refuses this interpreter (-60).
                # The code is the only thing that separates them, so it is reported, not dropped.
                why = (f"security status {status} (0x{status & 0xFFFFFFFF:08x})" if status
                       else f"unexpected secret length {size.value}")
                raise KeyUnavailable(f"purpose key unavailable or locked ({why})")
            return ctypes.string_at(content, size.value)
        finally:
            if content:
                security.SecKeychainItemFreeContent(None, content)
            if item:
                core.CFRelease(item)
            if keychain:
                core.CFRelease(keychain)


def peer_identity(sock) -> tuple[int, int]:
    """Darwin getpeereid: kernel UID/GID, never a caller-provided header."""
    if sys.platform != "darwin":
        raise KeyUnavailable("native peer identity unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.getpeereid
    function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
    function.restype = ctypes.c_int
    uid, gid = ctypes.c_uint(), ctypes.c_uint()
    if function(sock.fileno(), ctypes.byref(uid), ctypes.byref(gid)):
        raise KeyUnavailable("kernel peer identity unavailable")
    return uid.value, gid.value
