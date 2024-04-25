# mayanode

**mayanode** is a lightweight object-oriented approach for handling the scene in Maya. It offers a subset of Maya commands, focusing on individual node operations.

## Features

- **Intuitive**: This was built for ease of use, so abstracts a lot of the underlying functionality and simply works "as expected".
- **Efficiency**: The speed is comparable to `maya.cmds`[^1], and is far faster than `PyMel`.

- **Node Handling**: Create, query, and manipulate nodes within the Maya scene.
- **Attribute Management**: Interact with node attributes, including getting and setting values, keyframes, and connections.
- **Relationship Exploration**: Navigate through the scene hierarchy by accessing parents, children, ancestors, and descendants of nodes.
- **References**: Get and set data related to references. Not fleshed out yet.
- **UV/Color Sets**: Get and set data related to UV and color sets. Not fleshed out yet.
- **Namespace**: Get and set data and relationships related to namespaces. Not fleshed out yet.
- **Scene Data**: Convenient access to data related to the scene, such as the scene path, name, if modified, loaded plugins, etc. Not fleshed out yet.


## Installation

It is recommended to manually download this and place it somewhere in the system path.

Backwards compatibility between updates is not guaranteed.


## Usage

```python
# Import the Node class
>>> from mayanode import Node

# Get an existing node
>>> persp = Node('persp')
>>> persp.name
'persp'
>>> persp.longName
'|persp'
>>> persp.namespace
''


# Translating/rotating/scaling
>>> persp.translation = [10, 10, 10]  # Related: `rotation` / `scaling`
>>> persp.translate(-10, 0, 0)  # Related: `rotate` / `scale`
>>> persp.translation
Coordinate(x=0.0, y=10.0, z=10.0)


# Get relationships
>>> perspShape = perp.shape
>>> perspShape
Node('perspShape')
>>> perspShape.transform == perspShape.parent == persp
True
>>> perspShape in persp.children
True
>>> perspShape in persp.descendents
True
>>> persp in perspShape.ancestors
True
>>> persp.shadingEngine
None


# Get/set attribute
>>> 'depthOfField' in perspShape.attrs
True
>>> perspShape.attrs['depthOfField'] = True
>>> focusDist = perspShape.attrs['focusDistance']
>>> focusDist
Attribute('perspShape.focusDistance')
>>> focusDist.value = 3.52
>>> int(focusDist)
3
>>> focusDist.value
3.52


# Attribute connections
# Each connection has a "source" and "destination" for the direction,
# and "source" and "target" to determine the origin node
>>> persp.attrs['tx'] >> 'side.tx'
>>> 'side.ty' >> persp.attrs['ty']
>>> connection = persp.attrs['ty'].connections[0]
>>> connection
<Connection(source='side.translateY', destination='persp.translateY')>
>>> str(connection)
'side.translateY'
>>> connection.node  # It will always get the "target" node no matter the direction
Node('side')

# Optionally get just the source/destination connections
>>> persp.connections.destination
[<Connection(source='persp.translateX', destination='side.translateX')>]

# Break connections
>>> connection.disconnect()
>>> persp.attrs['tx'] // 'side.tx'
>>> persp.connections
[]


# Attribute states
>>> focusDist.keyable
True
>>> focusDist.locked
False
>>> focusDist.locked = True
>>> focusDist.value = 5
AttributeLockedError('The attribute "perspShape.focusDistance" is locked and cannot be modified.')


# Instances
>>> perspShape.instanced
False
>>> inst = persp.instance()
>>> persp.instanced
False
>>> perspShape.instanced
True
>>> inst
Node('persp1')
>>> inst.shape == perspShape
True


# Bounding box
bb = persp.boundingBox
>>> bb.width
4.475
>>> bb.x
-0.105
>>> bb.xMin
-2.343
>>> bb.origin
Coordinate(x=-0.105, y=10.159, z=9.895)
```


[^1]: On a per-node basis, when querying the scene, this can be a lot faster than `maya.cmds` as the OpenMaya API is used. Making changes is roughly equivalent as it does not use the API. Performing mass operations on entire scenes may potentially be slower due to the overhead of creating thousands of Python objects.
