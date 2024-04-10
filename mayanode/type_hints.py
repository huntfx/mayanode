"""Handle type hinting compatibility between Python 2 and 3.
`typing` is not installed by default so a workaround is required.
"""

TYPE_CHECKING = False  # Used for compatibility with the typing module

if TYPE_CHECKING:
    from typing import Union
    from . import types

    StrLike = Union[types.StrMixin, str]
