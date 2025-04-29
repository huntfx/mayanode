"""Handle type hinting compatibility between Python 2 and 3.
`typing` is not installed by default, and can cause issues, so a
workaround is required.
"""

__all__ = ['TYPE_CHECKING', 'cast', 'overload', 'StrLike']

TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import cast, overload
    from . import types

    StrLike = types.StrMixin | str

else:
    cast = lambda typ, var: var
    overload = lambda fn: fn  # pylint: disable=unnecessary-lambda-assignment
