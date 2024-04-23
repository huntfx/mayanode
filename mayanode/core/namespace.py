import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Optional
    from ..type_hints import StrLike


class Namespace(utils.StrMixin):
    """Handle namespaces.
    TODO: Tests
    """

    __slots__ = ['_namespace']

    def __init__(self, namespace):
        # type: (str) -> None
        self._namespace = ':' + ':'.join(map(om2.MNamespace.validateName, namespace.lstrip(':').split(':')))

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, Namespace):
            return self.name == other.name
        if not other:
            return self.name == ':'
        if other[0] == ':':
            return self.name == other
        return self.name[1:] == other

    def __bool__(self):
        # type: () -> bool
        return self.name not in (':', '')
    __nonzero__ = __bool__

    def __add__(self, other):
        # type: (StrLike) -> str
        return self.name + str(other)

    def __radd__(self, other):
        # type: (StrLike) -> str
        return other.rstrip(':') + self.name

    @classmethod
    def ls(cls):
        # type: () -> List[Namespace]
        """Get all namespaces within the scene."""
        return [cls(ns) for ns in om2.MNamespace.getNamespaces(recurse=True)]

    @classmethod
    def fromNode(cls, node):
        # type: (StrLike) -> Namespace
        """Get the namespace of a node.

        Returns:
            Namespace object or None.
        """
        if isinstance(node, Node):
            return cls(node.api.dependencyNode.namespace)
        return cls(om2.MNamespace.getNamespaceFromName(str(node)))

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the namespace exists."""
        return om2.MNamespace.namespaceExists(self.name)

    def create(self):
        # type: () -> None
        """Create the namespace.

        Raises:
            RuntimeError: A namespace of the given name '<ns>' already exists.
        """
        utils.logger.info('Creating namespace: %s', self)
        mc.namespace(add=self)

    def delete(self):
        # type: () -> None
        """Delete the namespace.

        Raises:
            RuntimeError: No namespace matches name: 'test'.
        """
        utils.logger.info('Deleting namespace: %s', self)
        mc.namespace(removeNamespace=self)

    @property
    def name(self):
        # type: () -> str
        """Get the namespace as a string."""
        return self._namespace

    @property
    def nodes(self):
        # type: () -> List[Node]
        """Get all nodes in the namespace."""
        if not self.name:
            return []
        return [Node(mobj) for mobj in om2.MNamespace.getNamespaceObjects(self.name)]

    @property
    def depth(self):
        # type: () -> int
        """Get the current depth of the namespace."""
        ns = self.name
        if ns == ':':
            return 0
        return self.name.count(':')

    @property
    def parent(self):
        # type: () -> Optional[Namespace]
        """Get the namespace parent."""
        ns = self.name
        if ns == ':':
            return None
        return self.fromNode(ns)

    @property
    def children(self):
        # type: () -> List[Namespace]
        """Get the direct children of the current namespace."""
        return [Namespace(child) for child in om2.MNamespace.getNamespaces(parentNamespace=self.name)]

    @property
    def ancestors(self):
        # type: () -> List[Namespace]
        """Get all ancestor namespaces starting with the parent and ending with ":"."""
        result = []
        new = self
        for _ in range(self.depth):
            new = self.fromNode(new.name)
            result.append(new)
        return result

    @property
    def descendents(self):
        # type: () -> List[Namespace]
        """Get all descendant namespaces."""
        return [Namespace(child) for child in om2.MNamespace.getNamespaces(parentNamespace=self.name, recurse=True)]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
