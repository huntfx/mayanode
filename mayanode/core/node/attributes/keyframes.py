from __future__ import absolute_import

try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

import maya.cmds as mc  # type: ignore

from .... import utils
from ....type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterable, Iterator, List, Optional, Tuple, Union


class AttributeKeyframes(MutableMapping):
    """Dictionary interface to keyframes on a specific attribute."""

    def __init__(self, attr):
        # type: (Attribute) -> None
        self.attr = attr
        super(AttributeKeyframes, self).__init__()

    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, self.attr)

    def __str__(self):
        # type: () -> str
        return dict(self.items()).__str__()

    def __len__(self):
        # type: () -> int
        return mc.keyframe(self.attr.node, attribute=self.attr.attr, query=True, keyframeCount=True)

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

    def keys(self):
        # type: () -> List[float]
        result = mc.keyframe(self.attr.node, attribute=self.attr.attr, query=True, timeChange=True)
        return result or []

    def values(self):
        # type: () -> List[float]
        result = mc.keyframe(self.attr.node, attribute=self.attr.attr, query=True, valueChange=True)
        return result or []

    def items(self):
        # type: () -> Iterator[Tuple[float, float]]
        result = mc.keyframe(self.attr.node, attribute=self.attr.attr, query=True, timeChange=True, valueChange=True)
        for i in range(0, len(result), 2):
            yield result[i], result[i+1]


class KeyframeProxy(object):
    """Controls for keyframes on a specific attribute and frame."""

    __slots__ = ['kf', 'frame']

    def __init__(self, keyframe, frame=None):
        # type: (AttributeKeyframes, Optional[Union[float, slice]]) -> None
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
            result = mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, keyframeCount=True, time=(self.frame, self.frame))
            if not result:
                return 0
            return result

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, keyframeCount=True, time=(frame, frame))
                if result:
                    results.append(result)
            return results

        return mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, keyframeCount=True, time=(self.frame.start, self.frame.stop - 1))

    @property
    def value(self):
        # type: () -> Optional[Union[List[float], float]]
        if not isinstance(self.frame, slice):
            result = mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame, self.frame))
            if not result:
                return None
            return result[0]

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(frame, frame))
                if result:
                    results.extend(result)
            return results

        return mc.keyframe(self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame.start, self.frame.stop - 1))

    def set(self, value=None, **kwargs):
        # type: (Optional[Union[float, Iterable[float]]], **Any) -> None
        utils.logger.info('Setting keyframe on "%s" (frame %s, value %s)', self.kf.attr, self.frame, value)

        args = [self.kf.attr.node]
        kwargs['attribute'] = self.kf.attr.attr
        kwargs['time'] = self.frame

        if isinstance(self.frame, slice):
            kwargs['time'] = list(range(self.frame.start, self.frame.stop, self.frame.step or 1))
        else:
            kwargs['time'] = self.frame

        if value is not None:
            kwargs['value'] = value

        mc.setKeyframe(*args, **kwargs)

    def delete(self):
        # type: () -> None
        utils.logger.info('Deleting keyframe on "%s" (frame %s)', self.kf.attr, self.frame)
        if not isinstance(self.frame, slice):
            mc.cutKey(self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame, self.frame))

        elif (self.frame.step or 1) != 1:
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                mc.cutKey(self.kf.attr.node, attribute=self.kf.attr.attr, time=(frame, frame))

        else:
            mc.cutKey(self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame.start, self.frame.stop))


# Handle circular dependencies
# pylint: disable=wrong-import-position
from . import Attribute
