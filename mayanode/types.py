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


class MappedLazyList(object):
    """Lazy list-like object that supports dict item mapping.

    Note:
        It is expected that the items will all result in unique strings when fed into `generateKey`.
        For optimisation purposes, this does not support using strings or None as list items.

    TODO:
        Add support for intermediate API types before they get converted.
            ie. Load plugs/UV set names etc separately.
        Allow duplicate keys to be mapped (eg. link "tx" to "translateX").
    """

    __slots__ = ['_data', '_mapping', '_unmapped', '_isDataLoaded', '_expectedLength', '_keyType']

    def __init__(self, data=None, keyType=None):
        # type: (Iterable[Any] | None, MappingKeyType | tuple[MappingKeyType, ...] | None) -> None
        """Set up the list.

        Parameters:
            data: Initial data to load.
                If this is given, then the list is assumed to be a set
                length.
            keyType: What type the mapping is.
                If `int`, then the list lookups will be overridden with
                the dict key counterpart.
        """
        self._isDataLoaded = False
        if data is None:
            self._data = []  # type: list[Any]
            self._expectedLength = None
        else:
            self._data = list(data)
            self._expectedLength = len(self._data)
        self._unmapped = []  # type: list[int]
        self._mapping = None  # type: dict[str, MappingKey] | None

        if not keyType or keyType in (str, unicode):
            keyType = (str, unicode)
        self._keyType = keyType

    def __repr__(self):
        # type: () -> str
        self._loadData()
        return self._data.__repr__()

    def __bool__(self):
        # type: () -> bool
        if self._data:
            return True
        if self._expectedLength is None:
            self._loadData()
        return bool(self._data)
    __nonzero__ = __bool__

    def __contains__(self, value):
        # type: (Any) -> bool
        self._loadData(value)
        if not isinstance(value, self._keyType):
            return value in self._data

        # If the mapping is already loaded then use that
        if self._mapping is not None:
            if value in self.mapping:
                return True

        # Check for a match in the actual data (if __eq__ is overridden)
        if value in self._data:
            return True

        # Finally load the mapping and check if it exists
        return value in self.mapping

    def __iter__(self):
        # type: () -> Iterator[Any]
        self._loadData()
        return self._data.__iter__()

    def __len__(self):
        # type: () -> int
        if self._expectedLength is None:
            self._loadData()
        if self._expectedLength is not None:
            return self._expectedLength
        return self._data.__len__()

    def __eq__(self, other):
        # type: (Any) -> bool
        self._loadData()
        return self._data == other

    def __ne__(self, other):
        # type: (Any) -> bool
        self._loadData()
        return self._data != other

    def _loadData(self, value=None):
        """Wrap the `loadData` method."""
        # Prevent re-running if all data is loaded
        if self._isDataLoaded:
            return

        # Run and check if all data is loaded
        if self.loadData(value):
            self._isDataLoaded = True

    def loadData(self, key=None):  # pylint: disable=unused-argument, no-self-use
        # type: (int | str | None) -> bool
        """Load all data or for a specific index or key.
        Requires override.

        An integer is for an index of the list. If the number of items
        is not known, then it is recommended to load all items.
        A string is to check for a dictionary mapping. If the mapping is
        still set to `None`, then it is recommended to load all items.
        An input of `None` is to request a load of all data.

        Returns:
            True if all data has been loaded.
        """
        return True

    def generateKey(self, value):
        # type: (Any) -> MappingKey
        """Override this to get the dict keys for each item."""
        return str(value)

    def _append(self, value):
        # type: (Any) -> None
        """Append to the list.
        This is for internal use only.
        """
        if value is None or isinstance(value, self._keyType):
            raise TypeError('"{}" not supported'.format(type(value).__name__))

        self._data.append(value)

        # Update the mapping data
        if self._mapping is not None:
            self._unmapped.append(len(self._data) - 1)

    def _insert(self, index, value):
        # type: (int, Any) -> None
        """Append to the list.
        This is for internal use only.
        """
        if value is None or isinstance(value, self._keyType):
            raise TypeError('"{}" not supported'.format(type(value).__name__))

        self._data.insert(index, value)

        # Update the mapping data
        if self._mapping is not None:
            for i, idx in enumerate(self._unmapped):
                if idx >= index:
                    self._unmapped[i] += 1
            for key, idx in self._mapping.items():
                if idx >= index:
                    self._mapping[key] += 1
            self._unmapped.append(index)

    def _setitem(self, index, value):
        # type: (int, Any) -> None
        """Set a value at an index.
        This is for internal use only.
        """
        self._data[index] = value
        if self._mapping is not None:
            if index < 0:
                index = len(self._data) - index - 1
            self._unmapped.append(index)

    def _set(self, values):
        # type: (Iterator[Any]) -> None
        """Replace the list with new data.
        This is for internal use only.
        """
        self._data[:] = list(values)
        self._mapping = None
        self._unmapped = []
        self._expectedLength = len(self._data)

    def _extend(self, value):
        # type: (Iterable[Any]) -> None
        """Update the list.
        This is for internal use only.
        """
        length = len(self._data)
        self._data.extend(value)
        self._expectedLength = len(self._data)

        # Update the mapping data
        if self._mapping is not None:
            self._unmapped.extend(range(length, len(self._data)))

    @property
    def mapping(self):
        # type: () -> dict[MappingKey, Any]
        """Get the mapping of keys to indexes."""
        if self._mapping is None:
            self._mapping = {self.generateKey(item): i for i, item in enumerate(self._data)}
        elif self._unmapped:
            self._mapping.update({self.generateKey(item): i for i, item
                                  in enumerate(map(self._data.__getitem__, self._unmapped))})
            self._unmapped[:] = []
        return self._mapping

    def __getitem__(self, value):
        # type: (slice | int | str) -> Any
        """Get the value at a specific key or index."""
        if isinstance(value, slice):
            for i in range(value.start, value.stop, value.step or 1):
                if self._data[i] is None:
                    self._loadData(i)
            return self._data[value]

        if isinstance(value, self._keyType):
            self._loadData(value)

        elif isinstance(value, int):
            if self._expectedLength is None or self._data[value] is None:
                self._loadData(value)
            return self._data[value]

        return self._data[self.mapping[value]]

    def get(self, value, default=None):
        # type: (Any, Any) -> Any
        """Get the value at a specific key, or fallback to a default value."""
        if isinstance(value, self._keyType):
            self._loadData(value)
        try:
            return self._data[self.mapping[value]]
        except KeyError:
            return default

    def keys(self):
        # type: () -> list[MappingKey]
        """Get all the mapped keys."""
        return list(self.mapping)

    def values(self):
        # type: () -> list[Any]
        """Get all of the data."""
        return list(self._data)

    def items(self):
        # type: () -> Iterator[tuple[MappingKey, Any]]
        """Get all the mapped items."""
        for k, v in self.mapping.items():
            yield k, self._data[v]

    def reload(self):
        # type: () -> None
        """Refresh the data."""
        if self._expectedLength is None:
            self._data[:] = []
        else:
            self._data[:] = [None for _ in range(self.__len__())]
        self._isDataLoaded = False


class MappedLazyList2(Generic[T_API, T_MOD, T_KEY]):

    __slots__ = ['_apiObjects', '_moduleObjects', '_mappedKeys', '_unloadCount']

    @property
    def _moduleType(self):  # type: () -> Type[T_MOD]
        raise NotImplementedError

    @property
    def _indexType(self):  # type: () -> Type[T_KEY]
        return str

    def _generateKeys(self, apiObject, moduleObject):
        # type: (T_API, T_MOD) -> Iterator[T_KEY]
        """Use the API object to get keys for the dict mapping."""
        return
        yield

    def _loadApiObjects(self):
        # type: () -> list[T_API]
        """Load all API objects."""
        raise NotImplementedError

    def __init__(self):
        # type: () -> None
        self._apiObjects = None  # type: list[T_API] | None
        self._moduleObjects = []  # type: list[T_MOD | None]
        self._mappedKeys = {}  # type: dict[str | int, int]
        self._unloadCount = 0

    def __repr__(self):
        # type: () -> str
        return repr(self._getModuleObjects())

    def __str__(self):
        # type: () -> str
        return str(self._getModuleObjects())

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, list):
            return self._getModuleObjects() == other
        return False

    def __bool__(self):
        # type: () -> bool
        """Determine if the attribute has any children."""
        return len(self) > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        """Get the number of child attributes."""
        return len(self._getApiObjects())

    def __iter__(self):
        # type: () -> Iterator[T_MOD]
        """Iterate through each child attribute."""
        return iter(self._getModuleObject(i) for i in range(len(self)))

    def __contains__(self, item):
        # type: (Any) -> bool
        """If a particular attribute is a child."""
        if isinstance(item, self._moduleType):
            return item in self._getModuleObjects()
        item = str(item)
        return item in self._getIndexes() or item in self._getModuleObjects()

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
        """Get an attribute from an index, name or slice."""
        # Get a list of attributes from a slice
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self._getModuleObject(i) for i in range(start, stop, step)]

        # Get the attribute at an index
        # If the index type is also an integer, then skip this part
        indexType = self._indexType
        if isinstance(index, int) and indexType is not int:
            return self._getModuleObject(index)

        # Get the attribute from its name
        self._ensureFullyLoaded()
        idx = self._getIndexes()[indexType(index)]
        return self._getModuleObjects()[idx]

    def get(self, item, default=None):
        # type: (Any, Any) -> Any
        """Return an item if it exists."""
        if item in self:
            return self[item]
        return default

    def keys(self):
        # type: () -> list[T_KEY]
        return list(self._getIndexes())

    def values(self):
        # type: () -> list[T_MOD]
        return list(self._getModuleObjects())

    def items(self):
        # type: () -> list[tuple[T_KEY, T_MOD]]
        objects = self._getModuleObjects()
        return [(k, objects[v]) for k, v in self._getIndexes().items()]

    def _getApiObjects(self):
        # type: () -> list[T_API]
        """Get a list of plugs to the child attributes."""
        result = self._apiObjects
        if result is None:
            result = self._apiObjects = self._loadApiObjects()
            count = self._unloadCount = len(result)
            self._moduleObjects = [None] * count
            self._mappedKeys.clear()
        return result

    def _getModuleObjects(self):
        # type: () -> list[T_MOD]
        """Get a list of child attributes."""
        self._ensureFullyLoaded()
        if TYPE_CHECKING:
            result = cast(list[T_MOD], self._moduleObjects)
        else:
            result = self._moduleObjects
        return result

    def _getIndexes(self):
        # type: () -> dict[T_KEY, int]
        """Get mapping of attribute names to their mapping index.
        The index can be used with `apiObjects` or `mappedObjects`.
        """
        self._ensureFullyLoaded()
        return self._mappedKeys

    def _ensureFullyLoaded(self):
        # type () -> None
        """Check that all the data is loaded."""
        self._getApiObjects()
        if self._unloadCount:
            for i, item in enumerate(self._moduleObjects):
                if item is None:
                    self._getModuleObject(i)

    def _getModuleObject(self, index):
        # type: (int) -> T_MOD
        """Get an individual attribute at an index.
        Creates a mapping if one doesn't exist.
        """
        apiObjects = self._getApiObjects()
        result = self._moduleObjects[index]
        if result is None:
            apiObject = apiObjects[index]
            result = self._moduleObjects[index] = self._loadModuleObject(apiObject)
            for key in self._generateKeys(apiObject, result):
                self._mappedKeys[key] = index
            self._unloadCount -= 1
        return result

    def _loadModuleObject(self, apiObject):
        # type: (T_API) -> T_MOD
        """Take an API object and load the corresponding module object."""
        return self._moduleType(apiObject)

    def refresh(self):
        # type: () -> None
        """Clear the data to be refreshed."""
        self._apiObjects = None



class _NodeType(StrMixin):
    """Base Node type for internal inheritance checks."""
