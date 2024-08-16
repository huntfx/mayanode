import os

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .node import Node
from .. import types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Union, Optional
    from ..type_hints import StrLike


class Reference(Node):
    """Handle references.
    TODO: Tests
    """

    @classmethod
    def ls(cls, *args, **kwargs):
        # type: (*StrLike, **Any)  -> List[Reference]
        """Get all references."""
        # Map to the class
        refNodes = [cls(refNode) for refNode in mc.ls(*args, references=True)]

        # Filter by loaded refs
        loaded = kwargs.get('loaded')  # type: Optional[bool]
        if loaded is not None:
            refNodes = [ref for ref in refNodes if ref.loaded == loaded]

        return refNodes

    @classmethod
    def fromFile(self, filepath):
        # type: (StrLike) -> List[Reference]
        """Get all references matching a file path."""
        refNodes = mc.ls(references=True)
        filepath = os.path.normpath(str(filepath))
        return [ref for ref in map(Reference, refNodes) if ref.filepath == filepath]

    @property
    def refNode(self):
        # type: () -> Reference
        return self

    @property
    def namespace(self):
        # type: () -> Namespace
        """Get the namespace of the reference.

        Note: It is possible to delete a namespace while a reference is
        unloaded. Upon reloading the reference, the associated namespace
        will be created only if the reference contains any nodes.

        Equivalent:
            `mc.referenceQuery(self, namespace=True)`
        """
        associatedNamespace = self.api.reference.associatedNamespace(False)
        if associatedNamespace:
            return Namespace(associatedNamespace)

        # If the namespace doesn't exist then fallback to the slower command
        return Namespace(mc.file(self.filepath, query=True, namespace=True))

    @namespace.setter
    def namespace(self, namespace):
        # type: (Union[Namespace, str]) -> None
        """Set a new namespace for the reference.

        TODO:
            Should this rename the existing one?
        """
        utils.logger.info('Setting new reference namespace for "%s": %s', self, namespace)
        mc.file(self.filepath, edit=True, namespace=namespace)

    @property
    def filepath(self):
        # type: () -> Optional[str]
        """Get the resolved reference file path.

        Equivalent:
            `mc.referenceQuery(self, filename=True, withoutCopyNumber=True)`

        Returns:
            The filepath or None.

        TODO:
            `ref.filepath.unresolved`
        """
        try:
            filepath = self.api.reference.fileName(resolvedName=True, includePath=False, includeCopyNumber=False)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise
        return os.path.normpath(filepath)

    @filepath.setter
    def filepath(self, filepath):
        # type: (str) -> None
        utils.logger.info('Setting new reference path for "%s": %s', self, filepath)
        mc.file(filepath, loadReference=self)

    @property
    def filename(self):
        # type: () -> Optional[str]
        """Get the reference filename.

        Equivalent:
            `mc.referenceQuery(self, filename=True, shortName=True, withoutCopyNumber=True)`

        Returns:
            The filename or None.
        """
        try:
            return self.api.reference.fileName(resolvedName=False, includePath=True, includeCopyNumber=False)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise

    @property
    def loaded(self):
        # type: () -> bool
        """Determine if the reference is loaded.

        Equivalent:
            `mc.referenceQuery(self, isLoaded=True)`
        """
        return self.api.reference.isLoaded()

    @loaded.setter
    def loaded(self, loaded):
        # type: (bool) -> None
        """Load or unload the reference."""
        if loaded:
            self.load()
        else:
            self.unload()

    def load(self):
        # type: () -> None
        """Load the reference."""
        utils.logger.info('Loading reference: %s', self)
        mc.file(loadReference=self)

    def unload(self):
        # type: () -> None
        utils.logger.info('Unloading reference: %s', self)
        mc.file(unloadReference=self)

    def delete(self):
        # type: () -> bool
        """Delete the reference.
        Returns if the reference was deleted.
        """
        if self.loaded:
            filename = self.api.reference.fileName(resolvedName=True, includePath=True, includeCopyNumber=True)
            mc.file(filename, removeReference=True)
            return True
        return False

    @property
    def nodes(self):
        # type: () -> ReferenceNodes
        """Get a list of nodes in the reference.
        This is slightly faster than using `ls` to search by namespace.

        Equivalent:
            `mc.referenceQuery(self, nodes=True)`
            `mc.ls(self.namespace + ':*')`
        """
        return ReferenceNodes(self)

    @property
    def locked(self):
        # type: () -> bool
        """Get if the reference is locked."""
        return self.api.reference.isLocked()

    @locked.setter
    def locked(self, locked):
        # type: (bool) -> None
        """Set the locked state of the reference."""
        if locked:
            self.lock()
        else:
            self.unlock()

    def lock(self):
        # type: () -> None
        """Lock the reference."""
        self.attrs['locked'].value = True

    def unlock(self):
        # type: () -> None
        """Unlock the reference."""
        self.attrs['locked'].value = False

    @property
    def topLevel(self):
        # type: () -> bool
        """Determine if the reference is a top level one."""
        return not self.refNode.api.dependencyNode.isFromReferencedFile

    @property
    def depth(self):
        # type: () -> int
        """Determine the depth of this reference.
        A top level reference will have a depth of 0.
        """
        depth = 0
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        mobject = self.refNode.api.object
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            fnRefNode = om2.MFnReference(refNode)
            if fnRefNode.containsNode(mobject):
                depth += 1
        return depth

    @property
    def parent(self):
        # type: () -> Optional[Reference]
        """Get the parent reference."""
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentObject = self.refNode.api.object
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            if refNode.containsNodeExactly(currentObject):
                return Reference(refNode)
        return None

    @property
    def ancestors(self):
        # type: () -> List[Reference]
        """Get all parent references."""
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentObject = self.refNode.api.object
        ancestors = []
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            if refNode.containsNode(currentObject):
                ancestors.append(Reference(refNode))
        return ancestors

    @property
    def children(self):
        # type: () -> List[Reference]
        """Get the nested child references."""
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentRefNode = self.api.reference
        children = []
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            if currentRefNode.containsNodeExactly(refNode):
                children.append(Reference(refNode))
        return children

    @property
    def descendents(self):
        # type: () -> List[Reference]
        """Get all nested child references and their children."""
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentRefNode = self.api.reference
        children = []
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            if currentRefNode.containsNode(refNode):
                children.append(Reference(refNode))
        return children


class ReferenceNodes(types.MappedLazyList):
    """Hold a list of all nodes in the reference.
    This also acts as a dict for the node names without their namespace.

    Example:
        >>> nodes = Reference('refNode').nodes
        >>> 'pCube1' in nodes
        True
        >>> nodes[0]
        Node('refNode:pCube1')
        >>> nodes['pCube1'] == nodes[0]
        True
        >>> len(nodes)
        1

    TODO:
        Tests
    """

    __slots__ = ['_reference', '_apiObjects']

    def __init__(self, reference):
        # type: (Reference) -> None
        self._reference = reference
        self._apiObjects = self.reference.api.reference.nodes()
        super(ReferenceNodes, self).__init__(None for _ in self._apiObjects)

    def __len__(self):
        return self._apiObjects.__len__()

    @property
    def reference(self):
        # type: () -> Reference
        """Get the associated reference."""
        return self._reference

    def __contains__(self, node):
        """If a particular node belongs to a reference."""
        if isinstance(node, Node):
            return self.reference.api.reference.containsNodeExactly(node.api.object)
        if isinstance(node, om2.MObject):
            return self.reference.api.reference.containsNodeExactly(node)
        return super(ReferenceNodes, self).__contains__(node)

    def generateKey(self, value):
        # type: (Any) -> str
        """Override this to get the dict keys for each item."""
        return str(value).split(':')[-1]

    def loadData(self, key=None):
        # type: (Optional[Union[int, str]]) -> bool
        """Get the node objects."""
        if self._apiObjects is None:
            self._apiObjects = self.reference.api.reference.nodes()

        # Load an index
        if isinstance(key, int):
            if self._data[key] is None:
                self._setitem(key, Node(self._apiObjects[key]))
            return False

        # Load all
        self._set(map(Node, self._apiObjects))
        return True

    def reload(self):
        # type: () -> None
        self._apiObjects = self.reference.api.reference.nodes()
        super(ReferenceNodes, self).reload()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .namespace import Namespace
