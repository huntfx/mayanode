from __future__ import absolute_import

try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

import maya.cmds as mc  # type: ignore

from .. import types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterable, Iterator, List, Optional, Tuple, Union


class KeyframeList(MutableMapping):
    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, self.node)

    def __str__(self):
        # type: () -> str
        return dict(self.items()).__str__()

    def __len__(self):
        # type: () -> int
        return mc.keyframe(self.attr.node, query=True, keyframeCount=True)

    def __iter__(self):
        # type: () -> Iterator[Any]
        return iter(self.keys())

    def __getitem__(self, frame):
        # type: (float) -> KeyframeProxy
        return KeyframeProxy(self, frame)

    def __setitem__(self, frame, value):
        # type: (float, float) -> None
        KeyframeProxy(self, frame).set(value)

    def __delitem__(self, frame):
        # type: (float) -> None
        KeyframeProxy(self, frame).delete()

    @property
    def node(self):
        """Get the node."""
        # type: () -> Node
        raise NotImplementedError

    @property
    def attr(self):
        # type: () -> Optional[Attribute]
        """Get the attribute."""
        return None

    @property
    def attribute(self):
        # type: () -> Optional[str]
        """Get the attribute name."""
        attr = self.attr
        if attr is None:
            return None
        return attr.attr

    def keys(self):
        # type: () -> List[float]
        result = mc.keyframe(self.node, attribute=self.attribute, query=True, timeChange=True)
        return result or []

    def values(self):
        # type: () -> List[float]
        result = mc.keyframe(self.node, attribute=self.attribute, query=True, valueChange=True)
        return result or []

    def items(self):
        # type: () -> Iterator[Tuple[float, float]]
        result = mc.keyframe(self.node, attribute=self.attribute, query=True, timeChange=True, valueChange=True)
        for i in range(0, len(result), 2):
            yield result[i], result[i+1]

    def delete(self, frame=None):
        # type: (Optional[Union[float, slice]]) -> int
        """Delete keyframes."""
        if frame is None:
            utils.logger.info('Deleting keyframe on "%s"', self.attr)
        else:
            utils.logger.info('Deleting keyframe on "%s" (frame %s)', self.attr, frame)

        result = 0
        if frame is None:
            result += mc.cutKey(self.node, attribute=self.attribute)

        elif not isinstance(frame, slice):
            result += mc.cutKey(self.node, attribute=self.attribute, time=(frame, frame))

        elif (frame.step or 1) != 1:
            for frame in range(frame.start, frame.stop, frame.step):
                result += mc.cutKey(self.node, attribute=self.attribute, time=(frame, frame))

        else:
            result += mc.cutKey(self.node, attribute=self.attribute, time=(frame.start, frame.stop))
        return result


class NodeKeyframes(KeyframeList):
    """Dictionary interface to keyframes on a specific node."""

    __slots__ = ['_node']

    def __init__(self, node):
        self._node = node
        super(NodeKeyframes, self).__init__()

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node


class AttributeKeyframes(KeyframeList):
    """Dictionary interface to keyframes on a specific attribute."""

    __slots__ = ['_attr']

    def __init__(self, attr):
        # type: (Attribute) -> None
        self._attr = attr
        super(AttributeKeyframes, self).__init__()

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self.attr.node

    @property
    def attr(self):
        # type: () -> Attribute
        """Get the attribute."""
        return self._attr


class KeyframeProxy(object):
    """Controls for keyframes on a specific attribute and frame."""

    __slots__ = ['kf', 'frame']

    def __init__(self, keyframe, frame=None):
        # type: (Union[NodeKeyframes, AttributeKeyframes], Optional[Union[float, slice]]) -> None
        self.kf = keyframe

        if frame is None:
            frame = mc.currentTime(query=True)

        self.frame = frame

    def __repr__(self):
        # type: () -> str
        return '{}({!r}, {})'.format(type(self).__name__, self.kf, self.frame)

    def __bool__(self):
        # type: () -> bool
        """Determine if any keyframes are set."""
        return bool(self.__len__())
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> Union[List[int], int]
        """Get the number of keyframes."""
        if not isinstance(self.frame, slice):
            result = mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, keyframeCount=True, time=(self.frame, self.frame))
            if not result:
                return 0
            return result

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, keyframeCount=True, time=(frame, frame))
                if result:
                    results.append(result)
            return results

        return mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, keyframeCount=True, time=(self.frame.start, self.frame.stop - 1))

    @property
    def value(self):
        # type: () -> Optional[Union[List[float], float]]
        """Get a keyframe value."""
        if not isinstance(self.frame, slice):
            result = mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, valueChange=True, time=(self.frame, self.frame))
            if not result:
                return None
            return result[0]

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, valueChange=True, time=(frame, frame))
                if result:
                    results.extend(result)
            return results

        return mc.keyframe(self.kf.node, attribute=self.kf.attribute, query=True, valueChange=True, time=(self.frame.start, self.frame.stop - 1))

    @value.setter
    def value(self, value):
        # type: (Optional[Union[float, Iterable[float]]]) -> None
        """Set a keyframe."""
        self.set(value)

    def set(self, value=None, **kwargs):
        # type: (Optional[Union[float, Iterable[float]]], **Any) -> int
        """Set a keyframe."""
        node = self.kf.node
        attr = self.kf.attr
        utils.logger.info('Setting keyframe on "%s" (frame %s, value %s)',
                          attr if attr is not None else node, self.frame, value)

        if attr is not None:
            kwargs['attribute'] = attr.attr

        if value is not None:
            kwargs['value'] = value

        if isinstance(self.frame, slice):
            kwargs['time'] = list(range(self.frame.start, self.frame.stop, self.frame.step or 1))
        else:
            kwargs['time'] = self.frame

        return mc.setKeyframe(node, **kwargs)

    def delete(self):
        # type: () -> int
        """Delete a keyframe."""
        return self.kf.delete(self.frame)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .node.attributes import Attribute
