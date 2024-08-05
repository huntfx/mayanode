try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence  # type: ignore[attr-defined]

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ...type_hints import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Tuple, Union
    from ...types import StrLike


class NodeTypes(MutableSequence):
    """Hold the data to load all matching node types.
    This is used instead of a list to allow certain optimisations.
    """

    __slots__ = ['_include', '_exclude', '_data']

    def __init__(self, include=None, exclude=None):
        # type: (Optional[str], Optional[str]) -> None
        """Store the data required to load the node types.
        If no inputs are given then all types will be returned.

        Note that currently there is no way to exclude abstract nodes,
        as there doesn't seem to be a good way to query if something is
        abstract or not.

        Parameters:
            include: Search for node type classifications.
                An example classification is 'shader'. This can be made
                more targeted with 'shader/surface' or 'shader/volume'.
                It can also target additional classifications, like
                'shader/texture:texture/2d'.

            exclude: Exclude a classification.

        See also:
            https://help.autodesk.com/view/MAYAUL/2020/ENU/index.html?contextId=COMMANDSPYTHON-LISTNODETYPES

        """
        if include is None:
            if exclude:
                raise ValueError('unable to exclude classification without include')
            self._include = None
        else:
            self._include = ':' + include.lower()
        self._exclude = ':' + (exclude or '').lower()
        self._data = None  # type: Optional[List[NodeType]]

    def _ensureLoaded(self):
        # type: () -> None
        """Load the plugin list."""
        if self._data is None:
            nodeTypes = None  # type: Any
            if self._include is None:
                nodeTypes = (nt.replace(' (abstract)') for nt in mc.allNodeTypes(includeAbstract=True))
            else:
                nodeTypes = mc.listNodeTypes(self._include, exclude=self._exclude) or ()
            self._data = [NodeType(nt) for nt in nodeTypes]

    def __contains__(self, item):
        # type: (object) -> bool
        """Check if a node is in the selection.
        If the selection has not yet been loaded, then just check the nodes
        """
        if not isinstance(item, (NodeType, str, type(u''))):
            return False

        # If the data is loaded, then check that
        # If no match, then proceed as it could be a new plugin
        if self._data is not None and item in self._data:
            return True

        # If all node types, just check it is a valid type
        if self._include is None:
            if isinstance(item, NodeType):
                return bool(item.id)
            return bool(om2.MNodeClass(item).typeId.id())

        # Get the node classification
        if isinstance(item, NodeType):
            classification = item.classification
        else:
            classification = om2.MNodeClass(item).classification
        if not classification:
            return False

        # Check if any of the classification is excluded
        if self._exclude:
            for exclude in self._exclude.split(':'):
                if exclude and ':' + exclude in classification:
                    return False

        # Check if any of the classification is included
        if self._include:
            for include in self._include.split(':'):
                if include and ':' + include not in classification:
                    return False

        return True

    def __str__(self):
        # type: () -> str
        self._ensureLoaded()
        if TYPE_CHECKING:
            assert self._data is not None
        return self._data.__str__()

    def __repr__(self):
        # type: () -> str
        self._ensureLoaded()
        if TYPE_CHECKING:
            assert self._data is not None
        return self._data.__repr__()

    @overload
    def __getitem__(self, index):
        # type: (int) -> NodeType
        pass

    @overload
    def __getitem__(self, index):
        # type: (slice) -> List[NodeType]
        pass

    def __getitem__(self, index):
        # type: (Union[int, slice]) -> Union[NodeType, List[NodeType]]
        """Get a node type at an index."""
        self._ensureLoaded()
        if TYPE_CHECKING:
            assert self._data is not None
        return self._data.__getitem__(index)

    def __len__(self):
        # type: () -> int
        """Get the number of nodes matching the classification."""
        self._ensureLoaded()
        if TYPE_CHECKING:
            assert self._data is not None
        return self._data.__len__()

    def __setitem__(self):
        raise TypeError('{!r} object does not support item assignment'.format(type(self).__name__))

    def __delitem__(self):
        raise TypeError('{!r} object does not support item assignment'.format(type(self).__name__))

    def insert(self, idx, item):
        raise TypeError('{!r} object does not support item assignment'.format(type(self).__name__))


class NodeType(str):
    """Get the current node type or what it inherits."""

    _TYPE_REGISTRY = {}  # type: Dict[str, NodeType]

    def __new__(cls, name):
        # type: (Union[int, om2.MTypeId, str]) -> NodeType
        """Create a singleton for each node type."""
        if isinstance(name, int):
            name = om2.MTypeId(name)
        if isinstance(name, om2.MTypeId):
            name = om2.MNodeClass(name).typeName
        if name not in cls._TYPE_REGISTRY:
            cls._TYPE_REGISTRY[name] = str.__new__(cls, name)
        return cls._TYPE_REGISTRY[name]

    def __init__(self, name):
        # type: (str) -> None
        self._mNodeClass = None  # type: Optional[om2.MNodeClass]
        self._inherited = None  # type: Optional[List[str]]
        self._derived = None  # type: Optional[List[str]]

    @classmethod
    def ls(cls, include=None, exclude=None):
        # type: (Optional[str], Optional[str]) -> NodeTypes
        """Get all matching node types."""
        return NodeTypes(include, exclude)

    @property
    def _apiNodeClass(self):
        # type: () -> om2.MNodeClass
        """Get the associated `MNodeClass` instance."""
        if self._mNodeClass is None:
            self._mNodeClass = om2.MNodeClass(self)
        return self._mNodeClass

    @property
    def inherited(self):
        # type: () -> List[str]
        """All base node types inherited by this type."""
        if self._inherited is None:
            # This is the same speed as `om2.MGlobal.getFunctionSetList()`
            self._inherited = mc.nodeType(self, isTypeName=True, inherited=True)
        return self._inherited

    @property
    def derived(self):
        # type: () -> List[str]
        """All currently known node types deriving from this type."""
        if self._derived is None:
            self._derived = mc.nodeType(self, isTypeName=True, derived=True)
        return self._derived

    @property
    def id(self):
        # type: () -> int
        """Get the type ID."""
        return self._apiNodeClass.typeId.id()

    @property
    def classification(self):
        # type: () -> str
        """Get the type classification."""
        return self._apiNodeClass.classification
