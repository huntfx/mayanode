"""Object orientated way of dealing with nodes.
This is a limited subset of Maya commands and not everything is available.

Examples:
    # Create a node
    >>> lambert = Node.create('lambert')
    Node('lambert2')

    # Get an existing node
    >>> cube = Node(mc.polyCube()[0])
    >>> cube.name
    'pCube1'
    >>> cube.name = 'myCube'
    >>> cube.longName
    '|myCube'
    >>> cube.namespace
    ''

    # Get/set relationships
    >>> cube.parent = 'persp'
    >>> Node('persp').children
    [Node('perspShape'), Node('pCube1')]
    >>> cube.shape
    Node('pCubeShape1')
    >>> Node('persp').descendents
    [Node('perspShape'), Node('myCube'), Node('pCubeShape1')]

    # Bounding box
    >>> bb = cube.boundingBox
    >>> bb.width
    1.0
    >>> bb.x
    0.0
    >>> bb.xMin
    -0.5
    >>> bb.origin
    Coordinate(x=0.0, y=0.0, z=0.0)

    # Transform node
    >>> cube.translation
    Coordinate(x=0, y=0, z=0)
    >>> cube.translation = (20, 20, 20)  # Absolute
    >>> cube.translate(-10, 0, 0)  # Relative
    >>> cube.rotatation = (0, 90, 0)
    >>> cube.scaling = (1, 2, 1)
    >>> cube.scale(1, 0.5, 1)

    # Attribute values
    >>> lambert.attrs['diffuse'] = 1
    >>> lambert.attrs['diffuse']
    NodeAttribute('myCube.diffuse')
    >>> lambert.attrs['diffuse'].value
    1.0
    >>> float(lambert.attrs['diffuse'])
    1.0
    >>> mc.getAttr(lambert + '.diffuse')
    1.0

    # Keyframes
    >>> kf = lambert.attrs['diffuse'].keyframes
    >>> kf.keys()
    []
    >>> kf[1] = 0
    >>> kf[3] = 0.5
    >>> kf[5] = 1
    >>> lambert.attrs['diffuse'].keyframes[3].value
    0.5

    # Attribute states
    >>> lambert.attrs['diffuse'].lock = True
    >>> lambert.attrs['diffuse'] = 0
    RuntimeError: setAttr: The attribute 'lambert2.diffuse' is locked or connected and cannot be modified.
    >>> lambert.attrs['diffuse'].keyable
    True

    # Keyframes
    >>> lambert.attrs['diffuse']

    # Get/set/break connections
    >>> 'lambert1.refractions' >> lambert.attrs['refractions']
    >>> lambert.attrs['diffuse'] >> 'lambert1.diffuse'
    >>> lambert.attrs['diffuse'] // 'lambert1.diffuse'
    >>> lambert.connections
    [<Connection(source='lambert1.refractions', destination='lambert2.refractions')>]
    >>> lambert.connections.nodes
    [Node(u'lambert1')]
    >>> lambert.connections.destination
    []

    # Instance
    >>> inst = cube.instance()
    >>> cube.instanced
    False
    >>> cube.shape.instanced
    True
    >>> cube.shape == inst.shape
    True

    # Reference
    >>> cube.referenced
    False
    >>> ref = Node('refNs:refObj').reference
    >>> ref
    Reference('refRN')
    >>> ref.loaded
    True
    >>> ref.nodes
    [Node('refNs:refObj'), ...]
    >>> ref.nodes['refObj']
    Node('refNs:refObj')

    # UV sets
    >>> cube.shape.uvSet
    UVSet('pCubeShape1.map1')
    >>> map2 = cube.shape.uvSets.create('map2')
    >>> map2.physicalIndex
    2
    >>> map2.name = 'bumpSet'
    >>> cube.shape.uvSets
    [UVSet('pCubeShape1.map1'), UVSet('pCubeShape1.bumpSet')]
"""

__all__ = [
    'exceptions',
    'Attribute',
    'Node',
    'BoundingBox',
    'Camera',
    'File',
    'Namespace',
    'Plugin',
    'Profiler',
    'ProgressBar',
    'Reference',
    'Scene',
    'Undo',
]

from . import exceptions
from .core.node import Node
from .core.node.attributes import Attribute
from .core.bounding_box import BoundingBox
from .core.camera import Camera
from .core.file import File
from .core.namespace import Namespace
from .core.plugin import Plugin
from .core.profiler import Profiler
from .core.progress_bar import ProgressBar
from .core.reference import Reference
from .core.scene import Scene
from .core.undo import Undo
