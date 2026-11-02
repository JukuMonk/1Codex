"""Exclusive lease for a specific local IB; reentrant only in the same thread."""
import contextlib
import hashlib
import os
from pathlib import Path
import threading


class BaseBusy(RuntimeError):
    pass


_local = threading.local()


@contextlib.contextmanager
def base_lease(project, database):
    identity = os.path.normcase(str(Path(database).resolve()))
    key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    held = getattr(_local, 'held', None)
    if held is None:
        held = _local.held = set()
    if key in held:
        yield
        return
    folder = Path(project)/'.platform/base-locks'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/(key+'.lock')).open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BaseBusy('База занята другим UI-прогоном или операцией платформы') from None
        held.add(key)
        try:
            yield
        finally:
            held.remove(key)
