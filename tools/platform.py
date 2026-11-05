"""Compatibility CLI; imports expose stdlib platform and lazy legacy helpers."""
import importlib.util as _util
import os as _os
import sysconfig as _sysconfig

_spec = _util.spec_from_file_location('_stdlib_platform', _os.path.join(_sysconfig.get_path('stdlib'), 'platform.py'))
_stdlib = _util.module_from_spec(_spec)
_spec.loader.exec_module(_stdlib)
for _name in dir(_stdlib):
    if not _name.startswith('__'): globals()[_name] = getattr(_stdlib, _name)

def __getattr__(name):
    import legacy_platform
    return getattr(legacy_platform, name)

if __name__ == '__main__':
    import runpy
    runpy.run_path(_os.path.join(_os.path.dirname(__file__), 'legacy_platform.py'), run_name='__main__')
