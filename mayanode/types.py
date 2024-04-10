from __future__ import absolute_import

from collections import namedtuple
try:
    from collections.abc import MutableMapping, MutableSequence
except ImportError:
    from collections import MutableMapping, MutableSequence

from . import type_hints

if type_hints.TYPE_CHECKING:
    from typing import Any, Dict, Iterable, Iterator, List, Optional, Union
    from typing import ItemsView, KeysView, ValuesView


Coordinate = namedtuple('Coordinate', ['x', 'y', 'z'])


class StrMixin(object):  # pylint: disable=useless-object-inheritance
    """Add methods to make the classes behave like strings."""

    __slots__ = []  # type: List[str]

    @property
    def name(self):
        # type: () -> str
        return ''

    def __str__(self):
        # type: () -> str
        return self.name

    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, StrMixin):
            return self.name == other.name
        return self.name == other

    def __ne__(self, other):
        # type: (Any) -> bool
        if isinstance(other, StrMixin):
            return self.name != other.name
        return self.name != other

    def __gt__(self, other):
        # type: (Any) -> bool
        return self.name > other

    def __ge__(self, other):
        # type: (Any) -> bool
        return self.name >= other

    def __lt__(self, other):
        # type: (Any) -> bool
        return self.name < other

    def __le__(self, other):
        # type: (Any) -> bool
        return self.name <= other

    def __contains__(self, value):
        # type: (str) -> bool
        return self.name.__contains__(value)

    def __hash__(self):
        # type: () -> int
        return hash(self.name)

    def split(self, *args, **kwargs):
        # type: (*Any, **Any) -> List[str]
        return self.name.split(*args, **kwargs)

    def rsplit(self, *args, **kwargs):
        # type: (*Any, **Any) -> List[str]
        return self.name.rsplit(*args, **kwargs)

    def startswith(self, value):
        # type: (str) -> bool
        return self.name.startswith(value)

    def endswith(self, value):
        # type: (str) -> bool
        return self.name.endswith(value)

    def strip(self, value):
        # type: (str) -> str
        return self.name.strip(value)

    def lstrip(self, value):
        # type: (str) -> str
        return self.name.lstrip(value)

    def rstrip(self, value):
        # type: (str) -> str
        return self.name.rstrip(value)


class LazyList(MutableSequence):
    """List-like object that is loaded only when needed.
    Values of `None` are not supported.
    """

    __slots__ = ['_data', '_isCorrectLength']

    def __init__(self, data=None):
        # type: (Optional[Iterable[Any]]) -> None
        """Set up the list.
        If `data` is given, then it is assumed to be of a set length.
        """
        if data is None:
            self._data = []
            self._isCorrectLength = False
        else:
            self._data = list(data)
            self._isCorrectLength = True

    def __repr__(self):
        # type: () -> str
        self._loadData()
        return self._data.__repr__()

    def __bool__(self):
        # type: () -> bool
        if self._data:
            return True
        if not self._isCorrectLength:
            self._loadData()
        return bool(self._data)
    __nonzero__ = __bool__

    def __iter__(self):
        # type: () -> Iterator[Any]
        self._loadData()
        return self._data.__iter__()

    def __getitem__(self, index):
        # type: (Union[int, slice]) -> Any
        """Get an individual item.

        If the list is of the correct length, then only load the item
        at the requested index. Otherwise, all items will have to be
        loaded.
        """
        if isinstance(index, slice):
            for i in range(index.start, index.stop, index.step):
                if self._data[i] is None:
                    self._loadData(i)

        elif not self._isCorrectLength or (self._isCorrectLength and self._data[index] is None):
            self._loadData(index)

        return self._data.__getitem__(index)

    def __setitem__(self, index, value):
        # type: (Any, Any) -> None
        raise AttributeError('__setitem__ not supported')

    def __delitem__(self, index):
        # type: (Any) -> None
        raise AttributeError('__delitem__ not supported')

    def append(self, value):
        # type: (Any) -> None
        raise AttributeError('append not supported')

    def insert(self, index, value):
        # type: (Any, Any) -> None
        raise AttributeError('insert not supported')

    def extend(self, values):
        # type: (Any) -> None
        raise AttributeError('extend not supported')

    def __len__(self):
        # type: () -> int
        if not self._isCorrectLength:
            self._loadData()
        return self._data.__len__()

    def __eq__(self, other):
        # type: (Any) -> bool
        self._loadData()
        return self._data == other

    def __ne__(self, other):
        # type: (Any) -> bool
        self._loadData()
        return self._data != other

    def __contains__(self, other):
        # type: (Any) -> bool
        self._loadData()
        return other in self._data

    def reload(self):
        # type: () -> None
        """Refresh the data."""
        self._data[:] = []

    def _loadData(self, index=None):
        # type: (Optional[int]) -> None
        """Load all data or for a specific index.
        Requires override.

        Parameters:
            idx (int, optional): Index of data.
        """


class LazyDict(MutableMapping):
    """Dict-like object that is loaded only when needed."""

    __slots__ = ['_data']

    def __init__(self):
        # type: () -> None
        self._data = {}  # type: Dict[str, Any]

    def __repr__(self):
        # type: () -> str
        self._loadData()
        return self._data.__repr__()

    def __getitem__(self, item):
        # type: (Any) -> Any
        self._loadData(item)
        return self._data.__getitem__(item)

    def __setitem__(self, item, value):
        # type: (Any, Any) -> None
        raise AttributeError('set not supported')

    def __delitem__(self, item):
        # type: (Any) -> None
        raise AttributeError('delete not supported')

    def update(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        raise AttributeError('update not supported')

    def clear(self):
        # type: () -> None
        raise AttributeError('clear not supported')

    def __iter__(self):
        # type: () -> Iterator[Any]
        self._loadData()
        return self._data.__iter__()

    def __len__(self):
        # type: () -> int
        self._loadData()
        return self._data.__len__()

    def __contains__(self, value):
        # type: (Any) -> bool
        self._loadData(value)
        return self._data.__contains__(value)

    def keys(self):
        # type: () -> KeysView[str]
        self._loadData()
        return self._data.keys()

    def values(self):
        # type: () -> ValuesView[Any]
        self._loadData()
        return self._data.values()

    def items(self):
        # type: () -> ItemsView[str, Any]
        self._loadData()
        return self._data.items()

    def _loadData(self, key=None):
        # type: (Optional[str]) -> None
        """Load all data or for a specific key.
        Requires override.

        Parameters:
            key (any, optional): Dictionary key.
        """
