import logging
import math
import os

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from . import exceptions
from .type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator, List, Optional, Union
    from .type_hints import StrLike


logger = logging.getLogger(__name__)

# Mapping of MEL to API types
MEL_API_TYPE = dict(
    transform=om2.MFn.kTransform,
    mesh=om2.MFn.kMesh,
    objectSet=om2.MFn.kSet,
    creaseSet=om2.MFn.kCreaseSet,
    animCurve=om2.MFn.kAnimCurve,
    shadingEngine=om2.MFn.kShadingEngine,
    light=om2.MFn.kLight,
    camera=om2.MFn.kCamera,
)

# MEL types that are valid DAG objects
DAG_TYPES = set(mc.nodeType('dagNode', derived=True, isTypeName=True))

TIME_UNITS = {
    'game': '15fps',
    'film': '24fps',
    'pal': '25fps',
    '29.97df': '29.97fps',
    'ntsc': '30fps',
    'show': '48fps',
    'palf': '50fps',
    'ntscf': '60fps',
}

_WORLD_HANDLE = None

_WORLD_DAG_PATH = None


class NotSet(object):  # pylint: disable=too-few-public-methods
    """Create a sentinel object for when a value isn't given.

    This is similar to using `NOT_SET = object()` but works with type
    checking.
    """


NOT_SET = NotSet()


def raiseIfNodeNotFound(node):
    # type: (Node) -> None
    """Raise an error if the node doesn't exist."""
    if not node.exists:
        if not node.api.object.isNull:
            raise exceptions.NullMObjectError
        raise exceptions.NodeDeletedError(node)


def addToRecentFiles(path):
    # type: (str) -> bool
    """Add a path to the recent files list.
    This could be done through the "RecentFilesList" optionVar,
    but that doesn't support removing duplicates.
    """
    if path.endswith('.ma'):
        fileType = 'mayaAscii'
    elif path.endswith('.mb'):
        fileType = 'mayaBinary'
    else:
        return False
    path = os.path.normpath(path).replace('\\', '/')
    mel.eval('addRecentFile("{}", "{}")'.format(path, fileType))
    return True


def unnetworkPlug(plug):
    # type: (om2.MPlug) -> om2.MPlug
    """Ensure an `MPlug` is not networked.

    In the majority of cases, this is just constucting a new plug using
    the data in the old one, but in the case of element plugs then they
    also require passing across the logical index.

    An example of this is when a reference is unloaded, all connections
    get pathed to `placeHolderList`. Connections are to elements in the
    array such as `placeHolderList[1]`, and have a logical index.
    TODO: Test
    """
    if not plug.isNetworked:
        return plug

    # Networked child plugs will lose their parent index
    # eg. `uvSet[1].uvSetName` becomes `uvSet[-1].uvSetName`
    # Maybe there's a better way, but it works by getting the parent,
    # which is not networked, then checking each child for a match with
    # the current plug
    # TODO: What happens if there's 2 compound ancestors?
    if plug.isChild:
        parent = plug.parent()
        return next(p for p in map(parent.child, range(parent.numChildren())) if p == plug)

    # Create an non networked copy of the plug
    new = om2.MPlug(plug.node(), plug.attribute())

    # If an element plug, then the index needs to be re-applied
    # eg. `uvSet[1]` becomes `uvSet[-1]` without this
    # Note that using `elementByLogicalIndex` creates a networked node
    if plug.isElement:
        new.selectAncestorLogicalIndex(plug.logicalIndex())

    return new


def constructionHistory(mobject, future=False):
    # type: (om2.MObject, bool) -> Iterator[om2.MObject]
    """Get the construction history of a node.
    Note that this will not automatically convert a transform to a mesh.

    Equivalent:
        `mc.listHistory(node)`
    """
    iterator = om2.MItDependencyGraph(mobject, om2.MFn.kInvalid,
                                      om2.MItDependencyGraph.kDownstream if future else om2.MItDependencyGraph.kUpstream,
                                      om2.MItDependencyGraph.kDepthFirst,
                                      om2.MItDependencyGraph.kNodeLevel)
    iterator.next()  # Skip the current node
    for _ in iterator:
        yield iterator.currentNode()


def getChildPlugs(plug):
    # type: (om2.MPlug) -> Iterator[om2.MPlug]
    """Recursively get all child plugs from a given plug.
    The current plug is also returned as the first item.
    """
    if plug.isNull:
        return

    yield plug

    if plug.isArray:
        childPlugs = map(plug.elementByPhysicalIndex, range(plug.numElements()))
    elif plug.isCompound:
        childPlugs = map(plug.child, range(plug.numChildren()))
    else:
        return

    for allChildPlugs in map(getChildPlugs, childPlugs):
        for childPlug in allChildPlugs:
            yield childPlug


def calculateTexelDensity(faces):
    # type: (Union[List[StrLike], StrLike]) -> float
    """Get the texel density value for the current UV set.
    Multiply the result to get the value for different map sizes.

    Reading the value on a different UV set is not supported.

    Equivalent:
        `texGetTexelDensity(1)`
    """
    area2D = sum(mc.polyEvaluate(faces, uvFaceArea=True))
    area3D = sum(mc.polyEvaluate(faces, worldFaceArea=True))
    return math.sqrt(area2D) / math.sqrt(area3D)


def setTexelDensity(faces, density):
    # type: (Union[List[StrLike], StrLike], float) -> None
    """Set the texel density value for the current UV set.

    The map size used is 1, so divide the density by the map size if
    required. For example, to set a density of 1024 for map size of
    4096, the density should be set to 0.25.

    Setting the value on a different UV set is not supported.

    Equivalent:
        `texSetTexelDensity(density, 1)`

    Raises:
        ZeroTexelDensityError: If texel density is zero.
    """
    originalSelection = mc.ls(selection=True)
    mc.select(faces)   # The `activeUVShells` flag doesn't work if node isn't selected

    for shell in mc.polyEvaluate(faces, activeUVShells=True):  # [0, 1, 2, ...]
        uvs = mc.polyEvaluate(faces, uvsInShell=shell)  # [node.map[0:100], ...]
        faces = mc.polyListComponentConversion(uvs, toFace=True, uvs=True)  # [node.f[0:100], ...]
        currentdensity = calculateTexelDensity(faces)
        try:
            scale = density / currentdensity
        except ZeroDivisionError:
            raise exceptions.ZeroTexelDensityError(faces)

        (u1, u2), (v1, v2) = mc.polyEvaluate(uvs, boundingBoxComponent2d=True)
        pU = (u1 + u2) / 2
        pV = (v1 + v2) / 2
        mc.polyEditUV(uvs, pivotU=pU, pivotV=pV, scaleU=scale, scaleV=scale)
    mc.select(originalSelection)


def getWorldHandle():
    # type: () -> om2.MObjectHandle
    """Get the handle to the world `MObject`.
    This is needed as it's parented to everything, but not wanted when
    querying DAG parents.
    """
    global _WORLD_HANDLE, _WORLD_DAG_PATH
    if _WORLD_HANDLE is not None:
        return _WORLD_HANDLE
    iterator = om2.MItDag(om2.MItDag.kDepthFirst, om2.MFn.kInvalid)
    world = iterator.currentItem()
    _WORLD_HANDLE = om2.MObjectHandle(world)
    _WORLD_DAG_PATH = om2.MDagPath.getAPathTo(world)
    return _WORLD_HANDLE


def getWorldDagPath():
    # type: () -> om2.MDagPath
    """Get the world `MDagPath`."""
    global _WORLD_DAG_PATH
    if _WORLD_DAG_PATH is None:
        getWorldHandle()
    return _WORLD_DAG_PATH


def toMObject(item):
    # type: (Any) -> Optional[om2.MObject]
    """Get the MObject from an input value if possible.
    Does not automatically convert strings.
    """
    if item is None:
        return om2.MObject.kNullObj
    if isinstance(item, om2.MObject):
        return item

    if isinstance(item, Node):
        return item.api.object
    return None


def iterAssemblies():
    # type: () -> Iterator[om2.MObject]
    """Get all assembly objects (top level transforms) in the scene."""
    worldDagPath = getWorldDagPath()
    for item in map(worldDagPath.child, range(worldDagPath.childCount())):
        if not item.hasFn(om2.MFn.kTransform) or item.hasFn(om2.MFn.kManipulator3D):
            continue
        depNode = om2.MFnDependencyNode(item)
        if depNode.isDefaultNode:
            continue
        yield item


def iterDG(apiType=om2.MFn.kInvalid):
    # type: (int) -> Iterator[om2.MObject]
    """Get all DG objects in the scene."""
    iterator = om2.MItDependencyNodes(apiType)

    if apiType == om2.MFn.kInvalid:
        world = getWorldHandle()
        for _ in iterator:
            item = iterator.thisNode()
            handle = om2.MObjectHandle(item)
            if handle != world:
                yield item

    else:
        for _ in iterator:
            yield iterator.thisNode()


def iterDAG(apiType=om2.MFn.kInvalid):
    # type: (int) -> Iterator[om2.MDagPath]
    """Get all DAG nodes (including instances) for an API type."""
    dagIterator = om2.MItDag(om2.MItDag.kDepthFirst, apiType)
    dagPathData = {}
    for _ in dagIterator:
        item = dagIterator.currentItem()

        if dagIterator.isInstanced():
            handle = om2.MObjectHandle(item).hashCode()
            if handle not in dagPathData:
                dagPathData[handle] = [dagIterator.getAllPaths(), 0]
            dagPaths, instanceNum = dagPathData[handle]

            yield dagPaths[instanceNum]
            dagPathData[handle][1] += 1

        else:
            yield dagIterator.getPath()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .core.node import Node
