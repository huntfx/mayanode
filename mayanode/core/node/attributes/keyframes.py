from __future__ import absolute_import

try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

import maya.cmds as mc  # type: ignore

from .... import utils
from ....type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator, Generator, List, Tuple


class AttributeKeyframes(MutableMapping):
    """Dictionary interface to keyframes on a specific attribute."""

    def __init__(self, attr):
        # type (Attribute) -> None
        self.attr = attr
        super(AttributeKeyframes, self).__init__()

    def __repr__(self):
        # type () -> str
        return '{}({!r})'.format(type(self).__name__, self.attr)

    def __str__(self):
        # type () -> str
        return dict(self.items()).__str__()

    def __len__(self):
        # type () -> int
        return len(self.keys())

    def __iter__(self):
        # type: () -> Iterator[Any]
        return iter(self.keys())

    def __getitem__(self, frame):
        # type (float) -> KeyframeProxy
        return KeyframeProxy(self, frame)

    def __setitem__(self, frame, value):
        # type (float) -> float
        KeyframeProxy(self, frame).set(value)

    def __delitem__(self, frame):
        # type (float) -> None
        KeyframeProxy(self, frame).delete()

    def keys(self):
        # type () -> List[float]
        result = utils.runAndLog(mc.keyframe, self.attr.node, attribute=self.attr.attr, query=True, timeChange=True)
        return result or []

    def values(self):
        # type () -> List[float]
        result = utils.runAndLog(mc.keyframe, self.attr.node, attribute=self.attr.attr, query=True, valueChange=True)
        return result or []

    def items(self):
        # type () -> Generator[Tuple[float, float]]
        result = utils.runAndLog(mc.keyframe, self.attr.node, attribute=self.attr.attr, query=True, timeChange=True, valueChange=True)
        for i in range(0, len(result), 2):
            yield result[i], result[i+1]


class KeyframeProxy(object):
    """Controls for keyframes on a specific attribute and frame."""

    __slots__ = ['kf', 'frame']

    def __init__(self, keyframe, frame=None):
        # type (AttributeKeyframes, Optional[Union[int, slice]]) -> None
        self.kf = keyframe

        if frame is None:
            frame = utils.runAndLog(mc.currentTime, query=True)

        self.frame = frame

    def __repr__(self):
        # type () -> str
        return '{}({!r}, {})'.format(type(self).__name__, self.kf, self.frame)

    @property
    def value(self):
        # type () -> Union[List[float], float]
        if not isinstance(self.frame, slice):
            result = utils.runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame, self.frame))
            if not result:
                return None
            return result[0]

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = utils.runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(frame, frame))
            return results

        return utils.runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame.start, self.frame.stop))

    def set(self, value=None):
        # type (Union[float, slice]) -> None
        utils.logger.info('Setting keyframe on "%s" (frame %s, value %s)', self.kf.attr, self.frame, value)

        args = [self.kf.attr.node]
        kwargs = dict(attribute=self.kf.attr.attr, time=self.frame)

        if isinstance(self.frame, slice):
            kwargs['time'] = list(range(self.frame.start, self.frame.stop, self.frame.step or 1))
        else:
            kwargs['time'] = self.frame

        if value is not None:
            kwargs['value'] = value

        utils.runAndLog(mc.setKeyframe, *args, **kwargs)

    def delete(self):
        # type () -> None
        utils.logger.info('Deleting keyframe on "%s" (frame %s)', self.kf.attr, self.frame)
        if not isinstance(self.frame, slice):
            utils.runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame, self.frame))

        elif (self.frame.step or 1) != 1:
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                utils.runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(frame, frame))

        else:
            utils.runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame.start, self.frame.stop))
