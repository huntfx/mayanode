from uuid import UUID

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ... import exceptions, types
from ...type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Dict, Generator, List, Optional, Tuple, Union
    from ...types import StrLike


class NodeType(str):
    """Get the current node type or what it inherits."""

    _TYPE_REGISTRY = {}  # type: Dict[str, NodeType]
    _CLASSIFICATION_REGISTRY = {}  # type: Dict[Tuple[str, str], List[NodeType]]

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
    def ls(cls, include=None, exclude=None, useCache=True):
        # type: (Optional[str], Optional[str], bool) -> List[NodeType]
        """Get all matching node types.
        If no inputs are given then all types will be returned.

        Note that currently there is no way to exclude abstract nodes,
        as there doesn't seem to be a good way to query if something is
        abstract or not.

        Parameters:
            include: Search for node type classifications.
                See link below for examples.
                An example classification is 'shader'. This can be made
                more targeted with 'shader/surface' or 'shader/volume'.
                It can also target additional classifications, like
                'shader/texture:texture/2d'.

            exclude: Exclude a classification.

            useCache: If cache should be used for faster lookups.
                Setting to False will update the cached data, which may
                be required after loading a plugin.

        See also:
            https://help.autodesk.com/view/MAYAUL/2020/ENU/index.html?contextId=COMMANDSPYTHON-LISTNODETYPES
        """
        key = (include or '', exclude or '')
        if not useCache or key not in cls._CLASSIFICATION_REGISTRY:

            # Search for a classification
            if include:
                nodeTypes = mc.listNodeTypes(include, exclude=exclude) or ()

            # Search for all types
            else:
                if exclude:
                    raise ValueError('unable to exclude classification without include')
                nodeTypes = (nt.replace(' (abstract)') for nt in mc.allNodeTypes(includeAbstract=True))

            cls._CLASSIFICATION_REGISTRY[key] = [cls(nt) for nt in nodeTypes]
        return cls._CLASSIFICATION_REGISTRY[key]

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
