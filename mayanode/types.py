from __future__ import absolute_import, division

import sys
from collections import namedtuple

import imath  # type: ignore
import maya.api.OpenMaya as om2

from .type_hints import TYPE_CHECKING, Generic, TypeVar, overload, cast

if TYPE_CHECKING:
    from typing import Any, Iterable, Iterator, Type
    from .type_hints import StrLike
    MappingKey = Any
    MappingKeyType = Type[MappingKey]
    Matrix16x1Type = tuple[float, float, float, float,
                           float, float, float, float,
                           float, float, float, float,
                           float, float, float, float]
    Matrix4x4Type = tuple[tuple[float, float, float, float],
                          tuple[float, float, float, float],
                          tuple[float, float, float, float],
                          tuple[float, float, float, float]]

if sys.version_info.major != 2:
    unicode = str  # pylint: disable=invalid-name

T = TypeVar('T')

T_API = TypeVar('T_API')

T_MOD = TypeVar('T_MOD')

T_KEY = TypeVar('T_KEY')

Coordinate = namedtuple('Coordinate', ['x', 'y', 'z'])


class Matrix4D(object):
    """Hold a 4D matrix."""

    def __init__(self, matrix=None):
        # type: (om2.MMatrix | Matrix16x1Type | Matrix4x4Type | None) -> None
        if matrix is None:
            self._matrix = imath.M44d()
        elif isinstance(matrix, imath.M44d):
            self._matrix = imath.M44d(matrix)
        elif isinstance(matrix, om2.MMatrix):
            self._matrix = imath.M44d(*matrix)
        elif len(matrix) == 4:
            self._matrix = imath.M44d(*map(tuple, matrix))
        elif len(matrix) == 16:
            self._matrix = imath.M44d(*matrix)
        else:
            raise TypeError('unsupported matrix format')

    def __repr__(self):
        return '{}(({}, {}, {}, {}))'.format(type(self).__name__, *self.rows)

    def __getitem__(self, item):
        # type: (int) -> None
        return self._matrix[item // 4][item % 4]

    def invert(self):
        # type: () -> None
        """In-place invert."""
        self._matrix.invert()

    def inverse(self):
        # type: () -> Matrix4D
        """Create new inverted list."""
        return Matrix4D(self._matrix.inverse())

    @property
    def rows(self):
        # type: () -> Matrix4x4Type
        """Iterate over each row of the matrix."""
        # Well this was a pain to keep mypy happy
        if TYPE_CHECKING:
            rows = ((self._matrix[0][1], self._matrix[0][2], self._matrix[0][3], self._matrix[0][4]),
                    (self._matrix[1][1], self._matrix[1][2], self._matrix[1][3], self._matrix[1][4]),
                    (self._matrix[2][1], self._matrix[2][2], self._matrix[2][3], self._matrix[2][4]),
                    (self._matrix[3][1], self._matrix[3][2], self._matrix[3][3], self._matrix[3][4]))
        else:
            rows = tuple(map(tuple, self._matrix))
        return rows


class StrMixin(object):  # pylint: disable=useless-object-inheritance
    """Add methods to make the classes behave like strings."""

    __slots__ = []  # type: list[str]

    @property
    def name(self):
        # type: () -> str
        return ''

    def __bool__(self):
        return bool(self.name)
    __nonzero__ = __bool__

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
        return not self.__eq__(other)

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

    def __add__(self, value):
        # type: (StrLike) -> str
        return self.name + value

    def __radd__(self, value):
        # type: (StrLike) -> str
        return value + self.name

    def split(self, *args, **kwargs):
        # type: (*Any, **Any) -> list[str]
        return self.name.split(*args, **kwargs)

    def rsplit(self, *args, **kwargs):
        # type: (*Any, **Any) -> list[str]
        return self.name.rsplit(*args, **kwargs)

    def startswith(self, value):
        # type: (str) -> bool
        return self.name.startswith(value)

    def endswith(self, value):
        # type: (str) -> bool
        return self.name.endswith(value)

    def strip(self, value=None):
        # type: (str | None) -> str
        return self.name.strip(value)

    def lstrip(self, value=None):
        # type: (str | None) -> str
        return self.name.lstrip(value)

    def rstrip(self, value=None):
        # type: (str | None) -> str
        return self.name.rstrip(value)

    def replace(self, old, new):
        # type: (str, str) -> str
        return self.name.replace(old, new)


class MappedLazyList(Generic[T_MOD, T_API, T_KEY]):
    """Hold a list of items with mappings to access them."""

    __slots__ = ['_apiObjects', '_listItems', '_mappedKeys', '_unloadCount']

    @property
    def ItemType(self):  # type: () -> Type[T_MOD]
        """Return the list item type.
        If this requires more than one argument, override the
        `_loadListItem` method.
        """
        raise NotImplementedError

    @property
    def IndexType(self):  # type: () -> Type[T_KEY]
        """Get the index type to use for the dict keys."""
        if TYPE_CHECKING:
            return cast(Type[T_KEY], str)
        return str

    def _generateKeys(self, apiObject, moduleObject):
        # type: (T_API, T_MOD) -> Iterator[T_KEY]
        """Generate possible keys to use for the dict mapping."""
        yield str(moduleObject)

    def _loadApiObjects(self):
        # type: () -> list[T_API]
        """Load all API objects."""
        raise NotImplementedError

    def _loadListItem(self, apiObject):
        # type: (T_API) -> T_MOD
        """Load the list item from the internal API object.
        This will require overriding if more than one argument.
        """
        return self.ItemType(apiObject)  # type: ignore[call-arg]

    def __init__(self):
        # type: () -> None
        self._apiObjects = None  # type: list[T_API] | None
        self._listItems = []  # type: list[T_MOD | None]
        self._mappedKeys = {}  # type: dict[T_KEY, int]
        self._unloadCount = 0

    def __repr__(self):
        # type: () -> str
        return repr(self._getListItems())

    def __str__(self):
        # type: () -> str
        return str(self._getListItems())

    def __eq__(self, other):
        # type: (Any) -> bool
        """Check if the list is equal."""
        if isinstance(other, list):
            return self._getListItems() == other
        return False

    def __bool__(self):
        # type: () -> bool
        """Determine if any list items exist."""
        return len(self) > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        """Get the number of list items."""
        return len(self._getApiObjects())

    def __iter__(self):
        # type: () -> Iterator[T_MOD]
        """Iterate over each list item."""
        return iter(self._getListItem(i) for i in range(len(self)))

    def __contains__(self, item):
        # type: (StrLike) -> bool
        """Check if a list item exists."""
        if isinstance(item, self.ItemType):
            return item in self._getListItems()
        item = str(item)
        return item in self._getIndexes() or item in self._getListItems()

    @overload
    def __getitem__(self, index):
        # type: (int | StrLike) -> T_MOD
        pass
    @overload
    def __getitem__(self, index):
        # type: (slice) -> list[T_MOD]
        pass
    def __getitem__(self, index):
        # type: (int | slice | StrLike) -> T_MOD | list[T_MOD]
        """Get a list item from an index, name or slice."""
        # Get a list of attributes from a slice
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self._getListItem(i) for i in range(start, stop, step)]

        # Get the attribute at an index
        # If the index type is also an integer, then skip this part
        indexType = self.IndexType
        if isinstance(index, int) and indexType is not int:
            return self._getListItem(index)

        # Get the attribute from its name
        self._ensureFullyLoaded()
        convertedIndex = indexType(index)  # type: ignore[call-arg]
        idx = self._getIndexes()[convertedIndex]
        return self._getListItems()[idx]

    def keys(self):
        # type: () -> list[T_KEY]
        """Get all mapped keys for the list items."""
        return list(self._getIndexes())

    def values(self):
        # type: () -> list[T_MOD]
        """Get all list items."""
        return list(self._getListItems())

    def items(self):
        # type: () -> list[tuple[T_KEY, T_MOD]]
        """Get a mapping of keys to list items."""
        objects = self._getListItems()
        return [(k, objects[v]) for k, v in self._getIndexes().items()]

    def _getApiObjects(self):
        # type: () -> list[T_API]
        """Get all the internal API objects."""
        result = self._apiObjects
        if result is None:
            result = self._apiObjects = self._loadApiObjects()
            count = self._unloadCount = len(result)
            self._listItems = [None] * count
            self._mappedKeys.clear()
        return result

    def _getListItems(self):
        # type: () -> list[T_MOD]
        """Get all the list objects."""
        self._ensureFullyLoaded()
        if TYPE_CHECKING:
            result = cast(list[T_MOD], self._listItems)
        else:
            result = self._listItems
        return result

    def _getIndexes(self):
        # type: () -> dict[T_KEY, int]
        """Get all the available mappings for the list items.
        The index is for the internal data.
        """
        self._ensureFullyLoaded()
        return self._mappedKeys

    def _ensureFullyLoaded(self):
        # type () -> None
        """Check that all the list items are loaded."""
        self._getApiObjects()
        if self._unloadCount:
            for i, item in enumerate(self._listItems):
                if item is None:
                    self._getListItem(i)

    def _getListItem(self, index):
        # type: (int) -> T_MOD
        """Get an individual item at an index."""
        apiObjects = self._getApiObjects()
        result = self._listItems[index]
        if result is None:
            apiObject = apiObjects[index]
            result = self._listItems[index] = self._loadListItem(apiObject)
            for key in self._generateKeys(apiObject, result):
                self._mappedKeys[key] = index
            self._unloadCount -= 1
        return result

    def refresh(self):
        # type: () -> None
        """Clear the data to be refreshed."""
        self._apiObjects = None


class LazyDict(Generic[T_KEY, T_MOD]):

    __slots__ = ['_items', '_invalidItems', '_loaded']

    @property
    def ItemType(self):  # type: () -> Type[T_MOD]
        """Return the dict value item type.
        If this requires more than one argument, override the
        `_loadListItem` method.
        """
        raise NotImplementedError

    @property
    def IndexType(self):  # type: () -> Type[T_KEY]
        """Get the index type to use for the mapping."""
        if TYPE_CHECKING:
            return cast(Type[T_KEY], str)
        return str

    def _loadIndividualObject(self, item):
        # type: (T_KEY) -> T_MOD | None
        """Get the dict value for a given key."""
        raise NotImplementedError

    def _loadAllObjects(self):
        # type: () -> list[T_MOD]
        """Get all possible dict values."""
        raise NotImplementedError

    def _generateKeys(self, item):
        # type: (T_MOD) -> Iterator[T_KEY]
        """Add rules on how to map keys to each value."""
        yield self.IndexType(item)  # type: ignore[call-arg]

    def __init__(self):
        # type: () -> None
        self._items = {}  # type: dict[T_KEY, T_MOD]
        self._invalidItems = set()  # type: set[T_KEY]
        self._loaded = False

    def __repr__(self):
        # type: () -> str
        return repr(self._getAllObjects())

    def __str__(self):
        # type: () -> str
        return str(self._getAllObjects())

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, dict):
            return self._getAllObjects() == other
        return False

    def __bool__(self):
        # type: () -> bool
        """Determine if any data exists."""
        if self._loaded:
            return bool(self._items)
        if self._items:
            return True
        return bool(self._getAllObjects())
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        return len(self._items)

    def __iter__(self):
        # type: () -> Iterator[T_KEY]
        """Iterate through each key."""
        return iter(self._getAllObjects().keys())

    def __contains__(self, item):
        # type: (T_KEY | T_MOD) -> bool
        """Check if an item exists in the dict.
        This checks both keys and values.
        """
        if isinstance(item, self.ItemType):
            if item in self._items.values():
                return True
            if self._loaded:
                return False
            self._loadAllObjects()
            return item in self._items.values()
        if TYPE_CHECKING: item = cast(T_KEY, item)
        return self._getIndividualObject(item) is not None

    def _getIndividualObject(self, key):
        # type: (T_KEY) -> T_MOD | None
        """Get the value for a given key."""
        if key in self._invalidItems:
            return None
        if key in self._items:
            return self._items[key]
        if self._loaded:
            return None

        item = self._loadIndividualObject(key)
        if item is None:
            self._invalidItems.add(key)
        else:
            for key in self._generateKeys(item):
                self._items[key] = item
        return item

    def _getAllObjects(self):
        # type: () -> dict[T_KEY, T_MOD]
        """Get all possible values."""
        if not self._loaded:
            for result in self._loadAllObjects():
                for key in self._generateKeys(result):
                    self._items[key] = result
        return self._items

    def __getitem__(self, item):
        # type: (Any) -> T_MOD
        """Get a value from a key."""
        result = self.get(item)
        if result is None:
            raise KeyError(item)
        return result

    def get(self, item, default=None):
        # type: (Any, T | None) -> T_MOD | T | None
        """Get a value from a key."""
        item = self.IndexType(item)  # type: ignore[call-arg]
        if self._loaded:
            return self._items[item]
        result = self._getIndividualObject(item)
        if result is None:
            return default
        return result

    def keys(self):
        # type: () -> list[T_KEY]
        return list(self._getAllObjects().keys())

    def values(self):
        # type: () -> list[T_MOD]
        return list(self._getAllObjects().values())

    def items(self):
        # type: () -> list[tuple[T_KEY, T_MOD]]
        return list(self._getAllObjects().items())

    def refresh(self):
        # type: () -> None
        """Clear the data to be refreshed."""
        self._items.clear
        self._invalidItems.clear()
        self._loaded = False


class _NodeType(StrMixin):
    """Base Node type for internal inheritance checks."""
