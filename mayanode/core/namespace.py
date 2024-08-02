import itertools

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..ext import classutilities
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Optional, Union
    from ..type_hints import StrLike



class NamespaceNodes(types.MappedLazyList):

    __slots__ = ['_namespace']

    def __init__(self, namespace):
        # type: (Namespace) -> None
        self._namespace = namespace
        super(NamespaceNodes, self).__init__()

    @property
    def namespace(self):
        # type: () -> Namespace
        """Get the associated namespace."""
        return self._namespace

    def __contains__(self, node, useMapping=None):
        # type: (StrLike, bool) -> bool
        """If a particular node belongs to a reference."""
        if isinstance(node, Node):
            return self.reference.api.reference.containsNodeExactly(node.api.object)
        if isinstance(node, om2.MObject):
            return self.reference.api.reference.containsNodeExactly(node)
        if not node:
            return False

        useMapping = '|' not in node and ':' not in node
        return super(NamespaceNodes, self).__contains__(node, useMapping=useMapping)  # type: ignore

    def generateKey(self, value):
        # type: (Any) -> str
        """Override this to get the dict keys for each item."""
        return str(value).split(':')[-1]

    def loadData(self, key=None):
        # type: (Optional[Union[int, str]]) -> bool
        """Get the node objects."""
        self._set(map(Node, om2.MNamespace.getNamespaceObjects(self.namespace.name)))
        return True

    def reload(self):
        # type: () -> None
        super(NamespaceNodes, self).reload()


class Namespace(classutilities.ClassPropertiesMixin, types.StrMixin):
    """Handle namespaces."""

    __slots__ = ['_namespace']

    def __init__(self, namespace=':'):  # pylint: disable=super-init-not-called
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

    @classutilities.classproperty
    @classmethod
    def root(cls):
        """Get the root namespace."""
        return cls(':')

    @classutilities.classproperty
    @classmethod
    def current(cls):
        # type: () -> Namespace
        """Get the current namespace."""
        return cls(mc.namespaceInfo(currentNamespace=True))

    @current.setter
    @classmethod
    def _currentSet(cls, value):
        # type: (Optional[StrLike]) -> None
        """Set the current namespace."""
        if not value:
            value = ':'
        elif not value.startswith(':'):
            value = ':' + value
        utils.logger.info('Setting current namespace: %s', value)
        if not om2.MNamespace.namespaceExists(value):
            raise exceptions.NamespaceNotFoundError(value)
        mc.namespace(set=value)

    @classmethod
    def findUnique(cls, namespace):
        # type: (StrLike) -> Namespace
        """Find a unique namespace based on the input string."""
        namespace = str(namespace)
        for i in itertools.count():
            if i:
                ns = Namespace(namespace + str(i))
            else:
                ns = Namespace(namespace)
            if not ns.exists:
                break
        return ns

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the namespace exists."""
        return om2.MNamespace.namespaceExists(self.name)

    def create(self):
        # type: () -> bool
        """Create the namespace.

        Returns:
            True if successful.
        """
        utils.logger.info('Creating namespace: %s', self)
        if self.exists:
            return False
        mc.namespace(add=self)
        return True

    def delete(self):
        # type: () -> bool
        """Delete the namespace.

        Raises:
            NamespaceNotEmptyError

        Returns:
            True if successful.
        """
        utils.logger.info('Deleting namespace: %s', self)
        if not self.exists:
            return False
        if om2.MNamespace.getNamespaces(parentNamespace=self.name):
            raise exceptions.NamespaceNotEmptyError(self)
        mc.namespace(removeNamespace=self)
        return True

    @property
    def name(self):
        # type: () -> str
        """Get the namespace as a string."""
        return self._namespace

    @property
    def nodes(self):
        # type: () -> NamespaceNodes
        """Get all nodes in the namespace."""
        return NamespaceNodes(self)

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
        if self.name == ':':
            return None
        return Namespace(om2.MNamespace.getNamespaceFromName(self.name))

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
            new = Namespace(om2.MNamespace.getNamespaceFromName(new.name))
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
