from __future__ import absolute_import

from collections import namedtuple
try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence



Coordinate = namedtuple('Coordinate', ['x', 'y', 'z'])


class StrMixin(object):  # pylint: disable=useless-object-inheritance
    """Add methods to make the classes behave like strings."""

    __slots__ = []

    def __str__(self):
        return self.name

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    def __contains__(self, value):
        return self.name.__contains__(value)

    def __hash__(self):
        return hash(self.name)

    def split(self, *args, **kwargs):
        return self.name.split(*args, **kwargs)

    def rsplit(self, *args, **kwargs):
        return self.name.rsplit(*args, **kwargs)

    def startswith(self, value):
        return self.name.startswith(value)

    def endswith(self, value):
        return self.name.endswith(value)


class LazyList(MutableSequence):
    """List-like object that is loaded only when needed.
    Values of `None` are not supported.
    """

    __slots__ = ['_data', '_isCorrectLength']

    def __init__(self, data=None):
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
        self._loadData()
        return self._data.__repr__()

    def __bool__(self):
        if self._data:
            return True
        if not self._isCorrectLength:
            self._loadData()
        return bool(self._data)
    __nonzero__ = __bool__

    def __iter__(self):
        self._loadData()
        return self._data.__iter__()

    def __getitem__(self, index):
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
        raise AttributeError('__setitem__ not supported')

    def __delitem__(self, index):
        raise AttributeError('__delitem__ not supported')

    def append(self, value):
        """Append an object to the end of the sequence."""
        raise AttributeError('append not supported')

    def insert(self, index, value):
        """Insert an object before an index."""
        raise AttributeError('insert not supported')

    def extend(self, values):
        """Insert an object before an index."""
        raise AttributeError('extend not supported')

    def __len__(self):
        if not self._isCorrectLength:
            self._loadData()
        return self._data.__len__()

    def __eq__(self, other):
        self._loadData()
        return self._data == other

    def __ne__(self, other):
        self._loadData()
        return self._data != other

    def __contains__(self, other):
        self._loadData()
        return other in self._data

    def reload(self):
        """Refresh the data."""
        self._data[:] = []

    def _loadData(self, index=None):
        """Load all data or for a specific index.
        Requires override.

        Parameters:
            idx (int, optional): Index of data.
        """
