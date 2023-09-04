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
    >>> cube.longName
    '|pCube1'
    >>> cube.namespace
    ''
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
    NodeAttribute('pCube1.diffuse')
    >>> lambert.attrs['diffuse'].value
    1.0
    >>> float(lambert.attrs['diffuse'])
    1.0
    >>> mc.getAttr(lambert + '.diffuse')
    1.0
    # Attribute states
    >>> lambert.attrs['diffuse'].lock = True
    >>> lambert.attrs['diffuse'] = 0
    RuntimeError: setAttr: The attribute 'lambert2.diffuse' is locked or connected and cannot be modified.
    >>> lambert.attrs['diffuse'].keyable
    True
    # Outgoing attribute connections
    >>> lambert.attrs['diffuse'] >> 'lambert1.diffuse'
    # Incoming connections
    >>> 'lambert1.refractions' >> lambert.attrs['refractions']
    # Rename node
    >>> attr = lambert.attrs['diffuse']
    >>> lambert.name = 'lambert3'
    >>> attr
    NodeAttribute('lambert3.diffuse')
    # Get relationships
    >>> cube.shape
    Node('pCubeShape1')
    >>> cube.shadingEngine
    Node('initialShadingGroup')
    >>> cube.parents
    []
    >>> cube.parent
    None
    # Instance
    >>> inst = cube.instance()
    >>> cube.instanced
    False
    >>> inst.instanced
    True
    >>> cube.shape == inst.shape
    True
"""

from . import exceptions
from .node import Node
from .bounding_box import BoundingBox
