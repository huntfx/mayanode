from __future__ import absolute_import

import maya.api.OpenMaya as om2  # type: ignore
import maya.api.OpenMayaAnim as oma2  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator, List, Optional, Set, Union


class KeyframeBase(object):
    __slots__ = []  # type: List[str]

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        attr = self.attr
        if attr is None:
            raise NotImplementedError
        return attr.node

    @property
    def attr(self):
        # type: () -> Optional[Attribute]
        """Get the associated attribute."""
        return None


class NodeKeyframes(KeyframeBase):
    __slots__ = ['_node', '_data']

    def __init__(self, node):
        # type: (Union[Node, NodeKeyframes]) -> None
        self._data = []  # type: List[AttributeKeyframes]

        if isinstance(node, NodeKeyframes):
            self._node = node.node
            self._data = node._data

        else:
            self._node = node
            currentNode = node  # type: Optional[Node]

            # Get connections from both the node and its shape
            # This matches the `mc.keyframe` behaviour
            for i in range(2):
                if i:
                    currentNode = node.shape
                    if currentNode is None:
                        continue

                for plug in currentNode.api.dependencyNode.getConnections():
                    for childPlug in utils.getChildPlugs(plug):
                        attr = Attribute(currentNode, childPlug)
                        self._data.append(AttributeKeyframes(attr))

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, self.node)

    def __len__(self):
        return sum(map(len, self._data))

    def __eq__(self, other):
        if isinstance(other, NodeKeyframes):
            return self._node == other._node
        return False

    def __iter__(self):
        # type: () -> Iterator[Keyframe]
        for kf in self._data:
            for frame in kf._keyframes:
                yield Keyframe(kf.attr, frame)

    def __contains__(self, frame):
        # type: (float) -> bool
        return any(frame in kf for kf in self._data)

    @property
    def frames(self):
        # type: () -> List[float]
        """Get all the keyframes on the node.

        Equivalent:
            `list(set(mc.keyframe(self.node, query=True, timeChange=True)))`
        """
        frames = set()  # type: Set[float]
        for kf in self._data:
            frames.update(kf._keyframes.keys())
        return list(sorted(frames))

    @property
    def attrs(self):
        # type: () -> List[Attribute]
        return [kf.attr for kf in self._data]

    def __getitem__(self, frame):
        # type: (Union[float, slice]) -> NodeKeyframeList
        """Get everything matching a frame.
        Ints, floats and slices are supported.

        Returns:
            Dict mapping attributes to a list of keyframes.
        """
        return NodeKeyframeList(self, frame)

    def __setitem__(self, frame, value):
        # type: (Union[float, slice], float) -> None
        Keyframe(self.node, frame).set(value)

    def set(self, value=None):
        # type: (Optional[float]) -> None
        Keyframe(self.node).set(value)

    def __delitem__(self, frame):
        # type: (Union[float, slice]) -> None
        Keyframe(self.node, frame).delete()

    def delete(self):
        # type: () -> None
        Keyframe(self.node).delete()


class NodeKeyframeList(KeyframeBase):
    __slots__ = ['_frame', '_kf']
    def __init__(self, nodeKeyframes, frame):
        # type: (Union[Node, NodeKeyframes], Optional[Union[float, slice]]) -> None
        if isinstance(nodeKeyframes, Node):
            nodeKeyframes = nodeKeyframes.keyframes
        elif not isinstance(nodeKeyframes, NodeKeyframes):
            raise TypeError(type(nodeKeyframes))

        self._frame = frame
        self._kf = nodeKeyframes

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._kf.node

    @property
    def _frames(self):
        # type: () -> Optional[List[float]]
        """Get the requested frames."""
        if self._frame is None:
            return None
        if isinstance(self._frame, (float, int)):
            return [float(self._frame)]
        if isinstance(self._frame, slice):
            frames = range(self._frame.start, self._frame.stop, self._frame.step or 1)
            return list(map(float, frames))
        raise TypeError(type(self._frame))

    def __iter__(self):
        frames = self._frames
        if frames is None:
            return iter(self._kf)
        return iter(kf for kf in self._kf if any(frame in kf for frame in frames))

    def set(self, value=None):
        # type: (Optional[float]) -> None
        Keyframe(self.node, self._frame).set(value)

    def delete(self):
        # type: () -> None
        Keyframe(self.node, self._frame).delete()


class AttributeKeyframes(KeyframeBase):
    __slots__ = ['_attr', '_keyframes']

    def __init__(self, attr):
        # type: (Attribute) -> None
        self._attr = attr
        self._keyframes = {}

        plug = attr.api.plug
        for otherPlug in plug.connectedTo(True, False):
            otherNode = otherPlug.node()
            if otherNode.hasFn(om2.MFn.kAnimCurve):
                animCurveFn = oma2.MFnAnimCurve(otherNode)
                numKeys = animCurveFn.numKeys
                for i in range(numKeys):
                    self._keyframes[animCurveFn.input(i).value] = animCurveFn.value(i)

    @property
    def attr(self):
        # type: () -> Attribute
        """Get the associated attribute."""
        return self._attr

    def __str__(self):
        # type: () -> str
        return '<{}({})>'.format(type(self).__name__, self._keyframes)

    def __repr__(self):
        # type: () -> str
        return '<{}({!r})>'.format(type(self).__name__, self._attr)

    def __len__(self):
        # type: () -> int
        """Get the number of keyframes."""
        return len(self._keyframes)

    def __iter__(self):
        # type: () -> Iterator[Keyframe]
        """Iterate over all the attribute keyframes."""
        return iter(Keyframe(self.attr, frame) for frame in self._keyframes)

    def __contains__(self, frame):
        # type: (float) -> bool
        """Determine if a keyframe exists."""
        return frame in self._keyframes

    def __getitem__(self, frame):
        # type: (Union[float, slice]) -> Keyframe
        """Get a keyframe."""
        return Keyframe(self.attr, frame)

    def __setitem__(self, frame, value):
        # type: (Union[float, slice], float) -> None
        """Set a keyframe."""
        Keyframe(self.attr, frame).set(value)

    def __delitem__(self, frame):
        # type: (Union[float, slice]) -> None
        """Delete a keyframe."""
        Keyframe(self.attr, frame).delete()

    @property
    def frames(self):
        # type: () -> List[float]
        """Get all the keyframes on the attribute.

        Equivalent:
            `mc.keyframe(self.node, attribute=self.attr.attr, query=True, timeChange=True)`
        """
        return list(self._keyframes.keys())

    @property
    def values(self):
        # type: () -> List[float]
        """Get all the keyframe values on the attribute.

        Equivalent:
            `mc.keyframe(self.node, attribute=self.attr.attr, query=True, valueChange=True)`
        """
        return list(self._keyframes.values())


class Keyframe(KeyframeBase):
    """Keyframe for a specific attribute.
    May be for a single frame or multiple.
    """

    __slots__ = ['_node', '_attr', 'frame']

    def __init__(self, attr, frame=None):
        # type: (Union[Node, Attribute], Optional[Union[float, slice]]) -> None
        if TYPE_CHECKING:
            self._attr = None  # type: Optional[Attribute]

        if isinstance(attr, Attribute):
            self._node = attr.node
            self._attr = attr
        elif isinstance(attr, Node):
            self._node = attr
            self._attr = None

        # If no frame is defined then use the current frame
        if frame is None:
            frame = mc.currentTime(query=True)
        self.frame = frame

    @property
    def attr(self):
        # type: () -> Optional[Attribute]
        """Get the associated attribute."""
        return self._attr

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    def __repr__(self):
        # type: () -> str
        item = self.attr  # type: Optional[Union[Node, Attribute]]
        if item is None:
            item = self.node
        return '{}({!r}, {})'.format(type(self).__name__, item, self.frame)

    def __bool__(self):
        # type: () -> bool
        """Determine if any keyframes are set."""
        return bool(self.__len__())
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> Union[List[int], int]
        """Get the number of keyframes."""
        node = self.node
        attr = self.attr
        frame = self.frame

        kwargs = {'query': True, 'keyframeCount': True}
        if attr is not None:
            kwargs['attribute'] = attr.attr

        if not isinstance(frame, slice):
            result = mc.keyframe(node, time=(frame, frame), **kwargs)
            if not result:
                return 0
            return result

        if (frame.step or 1) != 1:
            results = []
            for f in range(frame.start, frame.stop, frame.step):
                result = mc.keyframe(node, time=(f, f), **kwargs)
                if result:
                    results.append(result)
            return results

        return mc.keyframe(nodetime=(frame.start, frame.stop - 1), **kwargs)

    def get(self):
        # type: () -> Optional[Union[float, List[float]]]
        """Get a keyframe value."""
        node = self.node
        attr = self.attr
        frame = self.frame

        kwargs = {'query': True, 'valueChange': True}
        if attr is not None:
            kwargs['attribute'] = attr.attr

        if not isinstance(frame, slice):
            result = mc.keyframe(node, time=(frame, frame), **kwargs)
            if not result:
                return None
            return result[0]

        if (frame.step or 1) != 1:
            results = []
            for f in range(frame.start, frame.stop, frame.step):
                result = mc.keyframe(node, time=(f, f), **kwargs)
                if result:
                    results.extend(result)
            return results

        result = mc.keyframe(node, time=(frame.start, frame.stop - 1), **kwargs)
        if not result:
            return []
        return result

    def set(self, value=None, **kwargs):
        # type: (Optional[float], **Any) -> int
        """Set a keyframe."""
        node = self.node
        attr = self.attr
        frame = self.frame
        utils.logger.info('Setting keyframe on "%s" (frame %s, value %s)',
                          attr if attr is not None else node, frame, value)

        if attr is not None:
            kwargs['attribute'] = attr.attr

        if value is not None:
            kwargs['value'] = value

        if isinstance(frame, slice):
            kwargs['time'] = list(range(frame.start, frame.stop, frame.step or 1))
        else:
            kwargs['time'] = frame
        return mc.setKeyframe(node, **kwargs)

    def delete(self, **kwargs):
        # type: (**Any) -> int
        """Delete keyframes."""
        node = self.node
        attr = self.attr
        frame = self.frame

        if frame is None:
            utils.logger.info('Deleting keyframe on "%s"', attr if attr is not None else node)
        else:
            utils.logger.info('Deleting keyframe on "%s" (frame %s)', attr if attr is not None else node, frame)

        if attr is not None:
            kwargs['attribute'] = attr.attr

        result = 0
        if frame is None:
            result += mc.cutKey(node, **kwargs)

        elif not isinstance(frame, slice):
            result += mc.cutKey(node, time=(frame, frame), **kwargs)

        elif (frame.step or 1) != 1:
            for f in range(frame.start, frame.stop, frame.step):
                result += mc.cutKey(node, time=(f, f), **kwargs)

        else:
            result += mc.cutKey(node, time=(frame.start, frame.stop), **kwargs)
        return result

    @property
    def value(self):
        # type: () -> Optional[Union[List[float], float]]
        """Get a keyframe value."""
        return self.get()

    @value.setter
    def value(self, value):
        # type: (Optional[float]) -> None
        """Set a keyframe."""
        self.set(value)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute
from .node import Node
