"""Handle type hinting compatibility between Python 2 and 3.
`typing` is not installed by default, and can cause issues, so a
workaround is required.
"""

__all__ = ['TYPE_CHECKING', 'Generic', 'TypeVar', 'cast', 'overload', 'StrLike']

from six import with_metaclass

TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Generic, TypeVar, Union, cast, overload
    from . import types

    StrLike = types.StrMixin | str

else:
    cast = lambda typ, var: var
    overload = lambda fn: fn  # pylint: disable=unnecessary-lambda-assignment
    class _TypingMeta(type):
        def __getitem__(cls, item): return cls
    class Generic(with_metaclass(_TypingMeta)): pass
    class TypeVar(object):
        def __init__(self, *args, **kwargs): pass
    class Union(with_metaclass(_TypingMeta)):
        def __init__(self, *args, **kwargs): pass

