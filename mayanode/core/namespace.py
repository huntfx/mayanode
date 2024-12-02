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

    def __contains__(self, node):
        # type: (StrLike) -> bool
        """If a particular node belongs to a namespace."""
        if isinstance(node, Node):
            return node.namespace == self.namespace
        return super(NamespaceNodes, self).__contains__(node)

    def generateKey(self, value):
        # type: (Any) -> str
        """Override this to get the dict keys for each item."""
        return str(value).split(':')[-1]

    def loadData(self, key=None):
        # type: (Optional[Union[int, str]]) -> bool
        """Get the node objects."""
        self._set(map(Node, om2.MNamespace.getNamespaceObjects(str(self.namespace))))
        return True

    def reload(self):
        # type: () -> None
        super(NamespaceNodes, self).reload()


class Namespace(classutilities.ClassPropertiesMixin, types.StrMixin):
    """Handle namespaces."""

    __slots__ = ['_namespace']

    def __init__(self, namespace=':'):  # pylint: disable=super-init-not-called
        # type: (str) -> None
        self._namespace = utils.validateNamespace(namespace)

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

    def strip(self, value=None):
        # type: (Optional[str]) -> str
        name = super(Namespace, self).strip(value)
        if value is None:
            return name.strip(':')
        return name

    def lstrip(self, value=None):
        # type: (Optional[str]) -> str
        name = super(Namespace, self).lstrip(value)
        if value is None:
            return name.lstrip(':')
        return name

    def rstrip(self, value=None):
        # type: (Optional[str]) -> str
        name = super(Namespace, self).rstrip(value)
        if value is None:
            return name.rstrip(':')
        return name

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

    def delete(self, recursive=False, nodes=False):
        # type: (bool, bool) -> List[Namespace]
        """Delete the namespace.

        Raises:
            NamespaceNotEmptyError

        Returns:
            Deleted namespaces.
        """
        utils.logger.info('Deleting namespace: %s (recursive: %s, nodes: %s)', self, recursive, nodes)
        if not self.exists:
            return 0

        # Check if any child namespaces exist
        childNamespaces = om2.MNamespace.getNamespaces(parentNamespace=self.name, recurse=recursive)

        # If not a recursive delete, then fail
        if childNamespaces and not recursive:
            raise exceptions.NamespaceNotEmptyError(self)

        namespaces = [self.name] + childNamespaces

        # Check if any nodes exist
        nodesToDelete = []
        for namespace in namespaces:
            nsObjects = om2.MNamespace.getNamespaceObjects(namespace)
            if nsObjects:
                if nodes:
                    nodesToDelete.extend(depNode.name() for depNode in map(om2.MFnDependencyNode, nsObjects))
                else:
                    raise exceptions.NamespaceNotEmptyError(self)

        if nodesToDelete:
            mc.delete(nodesToDelete)
        for namespace in reversed(namespaces):
            mc.namespace(removeNamespace=namespace)
        return namespaces

    @property
    def name(self):
        # type: () -> str
        """Get the namespace as a string."""
        return self._namespace

    @name.setter
    def name(self, name):
        # type: (Any) -> None
        """Rename the namespace.
        Any required parent namespaces will be automatically created.

        Raises:
            NamespaceInvalidNameError
            NamespaceNotUniqueError
        """
        utils.logger.info('Renaming "%s" to "%s"', self, name)
        name = namespace = utils.validateNamespace(name)
        name = name.lstrip(':')

        if not name:
            raise exceptions.NamespaceInvalidNameError(self)
        if om2.MNamespace.namespaceExists(name):
            if self == name:
                return
            raise exceptions.NamespaceNotUniqueError(name)

        kwargs = {}

        # Handle parents
        if ':' in name:
            parent, name = name.rsplit(':', 1)
            parent = Namespace(parent)
            if not parent.exists:
                parent.create()
            kwargs['parent'] = parent

        mc.namespace(rename=(self, name), **kwargs)
        self._namespace = namespace

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

    @property
    def reference(self):
        # type: () -> Optional[Reference]
        """Get the associated reference node."""
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())

            # If the namespace exists then it can be directly queried
            if self.exists:
                namespace = refNode.associatedNamespace(False)

            # If it doesn't exist, then it's still possible a reference has it
            else:
                filename = refNode.fileName(resolvedName=True, includePath=False, includeCopyNumber=True)
                namespace = mc.file(filename, query=True, namespace=True)

            if namespace == self:
                return Reference(refNode)
        return None


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .reference import Reference
