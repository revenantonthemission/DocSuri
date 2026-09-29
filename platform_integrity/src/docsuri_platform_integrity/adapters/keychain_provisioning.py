"""Explicit custom-Keychain create/unlock through Security.framework; no secret argv or files."""

import ctypes
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from .keychain import KeyUnavailable


class Attribute(ctypes.Structure):
    _fields_ = [("tag", ctypes.c_uint32), ("length", ctypes.c_uint32),
                ("data", ctypes.c_void_p)]


class AttributeList(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32), ("attributes", ctypes.POINTER(Attribute))]


class KeychainOperationError(KeyUnavailable):
    def __init__(self, operation, status):
        self.operation, self.status = operation, int(status)
        super().__init__(f"keychain {operation} failed ({self.status})")


class NativeKeychain:
    def __init__(self):
        if sys.platform != "darwin":
            raise KeyUnavailable("native macOS Keychain required")
        self.security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        self.core = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        p, u = ctypes.c_void_p, ctypes.c_uint32
        signatures = {
            "SecKeychainSetUserInteractionAllowed": [ctypes.c_bool],
            "SecKeychainCreate": [ctypes.c_char_p, u, p, ctypes.c_bool, p, ctypes.POINTER(p)],
            "SecKeychainOpen": [ctypes.c_char_p, ctypes.POINTER(p)],
            "SecKeychainUnlock": [p, u, p, ctypes.c_bool],
            "SecKeychainLock": [p],
            "SecKeychainDelete": [p],
            "SecKeychainItemCreateFromContent": [u, ctypes.POINTER(AttributeList), u, p,
                                                  p, p, ctypes.POINTER(p)],
            "SecTrustedApplicationCreateFromPath": [ctypes.c_char_p, ctypes.POINTER(p)],
            "SecAccessCreate": [p, p, ctypes.POINTER(p)],
        }
        for name, args in signatures.items():
            function = getattr(self.security, name)
            function.argtypes, function.restype = args, ctypes.c_int32
        self.core.CFRelease.argtypes = [p]
        self.core.CFRelease.restype = None
        self.core.CFStringCreateWithCString.argtypes = [p, ctypes.c_char_p, u]
        self.core.CFStringCreateWithCString.restype = p
        self.core.CFArrayCreate.argtypes = [p, ctypes.POINTER(p), ctypes.c_long, p]
        self.core.CFArrayCreate.restype = p
        self._check("disable_interaction",
                    self.security.SecKeychainSetUserInteractionAllowed(False))

    @staticmethod
    def _check(operation, status):
        if status:
            raise KeychainOperationError(operation, status)

    @staticmethod
    def _password(value):
        raw = value.encode("utf-8")
        if not 12 <= len(raw) <= 1024 or b"\x00" in raw:
            raise ValueError("keychain password length must be 12..1024 UTF-8 bytes")
        return ctypes.create_string_buffer(raw), len(raw)

    def _release(self, *values):
        for value in values:
            if value:
                self.core.CFRelease(value)

    @contextmanager
    def opened(self, path, *, owner=None):
        # `owner` is explicit so a root-run provisioner can create and inspect a keychain on
        # behalf of the signing role instead of relying on the caller's own identity.
        expected = os.geteuid() if owner is None else owner
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != expected
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise KeyUnavailable("keychain file is unprotected")
        handle = ctypes.c_void_p()
        self._check("open", self.security.SecKeychainOpen(os.fsencode(path), ctypes.byref(handle)))
        try:
            yield handle
        finally:
            self._release(handle)

    def create(self, path: Path, password: str, service: str, account: str, secret: bytes,
               executable: Path, *, owner=None):
        expected = os.geteuid() if owner is None else owner
        if path.exists() or path.is_symlink():
            raise FileExistsError("keychain already exists; use explicit unlock/recovery")
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != expected
            or stat.S_IMODE(parent.st_mode) != 0o700):
            raise KeyUnavailable("keychain directory must be role-owned 0700")
        if (not service or not account or max(len(service.encode()), len(account.encode())) > 200
            or "\x00" in service + account or len(secret) != 32):
            raise ValueError("invalid signing item")
        buffer, length = self._password(password)
        secret_buffer = ctypes.create_string_buffer(secret)
        trusted, access, keychain, item = (ctypes.c_void_p() for _ in range(4))
        title = applications = None
        created = False
        try:
            self._check("trusted_application", self.security.SecTrustedApplicationCreateFromPath(
                os.fsencode(executable.resolve(strict=True)), ctypes.byref(trusted)))
            applications = self.core.CFArrayCreate(
                None, (ctypes.c_void_p * 1)(trusted.value), 1, None)
            title = self.core.CFStringCreateWithCString(
                None, b"DocSuri receipt signing", 0x08000100)
            if not applications or not title:
                raise KeyUnavailable("keychain access allocation failed")
            self._check("access", self.security.SecAccessCreate(title, applications,
                                                                ctypes.byref(access)))
            previous_umask = os.umask(0o077)
            try:
                self._check("create", self.security.SecKeychainCreate(
                    os.fsencode(path), length, buffer, False, access, ctypes.byref(keychain)))
            finally:
                os.umask(previous_umask)
            created = True
            path.chmod(0o600)
            service_buffer = ctypes.create_string_buffer(service.encode())
            account_buffer = ctypes.create_string_buffer(account.encode())
            attributes = (Attribute * 2)(
                Attribute(int.from_bytes(b"svce", "big"), len(service.encode()),
                          ctypes.cast(service_buffer, ctypes.c_void_p)),
                Attribute(int.from_bytes(b"acct", "big"), len(account.encode()),
                          ctypes.cast(account_buffer, ctypes.c_void_p)),
            )
            attribute_list = AttributeList(2, attributes)
            # Set the restricted ACL at creation; a later ACL edit can require interactive
            # authorization even after keychain interaction has been disabled.
            self._check("add_item", self.security.SecKeychainItemCreateFromContent(
                int.from_bytes(b"genp", "big"), ctypes.byref(attribute_list), len(secret),
                secret_buffer, keychain, access, ctypes.byref(item)))
            path.chmod(0o600)
        except BaseException:
            # Only the fresh keychain created by this invocation is eligible for cleanup.
            if created:
                self.security.SecKeychainDelete(keychain)
            raise
        finally:
            ctypes.memset(buffer, 0, ctypes.sizeof(buffer))
            ctypes.memset(secret_buffer, 0, ctypes.sizeof(secret_buffer))
            self._release(item, keychain, access, applications, title, trusted)

    def unlock(self, path: Path, password: str, *, owner=None):
        buffer, length = self._password(password)
        try:
            with self.opened(path, owner=owner) as keychain:
                self._check("unlock", self.security.SecKeychainUnlock(
                    keychain, length, buffer, True))
        finally:
            ctypes.memset(buffer, 0, ctypes.sizeof(buffer))

    def lock(self, path: Path, *, owner=None):
        with self.opened(path, owner=owner) as keychain:
            self._check("lock", self.security.SecKeychainLock(keychain))

    def delete_disposable(self, path: Path, *, owner=None):
        """Used by explicit disposable-keychain verification, never by normal signer operation."""
        with self.opened(path, owner=owner) as keychain:
            self._check("delete", self.security.SecKeychainDelete(keychain))
