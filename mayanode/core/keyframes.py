from __future__ import absolute_import

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as mc  # type: ignore

from .. import exceptions, utils
from ..type_hints import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Any, Iterator


def _getKtvPlug(plug):
    # type: (om2.MPlug) -> om2.MPlug | None
    """Get the ktv plug for an attribute."""
    if not plug.isDestination:
        return None
    curvePlug = plug.source()
    curveNode = curvePlug.node()
    return om2.MFnDependencyNode(curveNode).findPlug('keyTimeValue', False)


def _toTime(value, setKeyframe=False):
    # type: (slice | float | None, bool) -> Iterator[tuple[str | int | float, ...]]
    """Convert an input to a time tuple compatible with `mc.keyframe`.
    Since slices may need multiple calls, this is an iterator.
    """
    if value is None:
        yield ()

    elif isinstance(value, (int, float)):
        yield float(value),

    elif isinstance(value, slice):
        _validateSlice(value)

        if setKeyframe and (value.start is None or value.stop is None):
            raise ValueError('incomplete slice not compatible with setKeyframe')

        if value.start is not None and value.stop is not None:
            if (value.step or 1) == 1:
                if setKeyframe:
                    yield tuple(range(value.start, value.stop + 1))
                else:
                    yield (value.start, value.stop)
            else:
                frames = range(int((value.stop + value.step) // value.step))
                if setKeyframe:
                    yield tuple(value.start + i * value.step for i in frames)
                else:
                    for i in frames:
                        yield value.start + i * value.step,

        # TODO: Add below code to tests or determine if it's not needed
        elif value.start is None:
            if value.stop is None:
                yield ()
            else:
                yield ':{}'.format(value.stop),
        else:
            yield '{}:'.format(value.start),

    else:
        raise TypeError(type(value))


def _validateSlice(value):
    # type: (Any) -> None
    """Check a slice is valid.
    For the time being, if a slice is missing a start or end value,
    then steps are not supported.
    """
    if not isinstance(value, slice):
        return
    if value.start is not None and value.stop is not None:
        return
    if value.step in (None, 1):
        return
    raise ValueError('step not supported with incomplete slice')


class KeyframeBase(object):
    __slots__ = ['_frame']  # type: list[str]

    def __init__(self, frame=None):
        # type: (float | slice | None) -> None
        _validateSlice(frame)
        self._frame = frame

    def __bool__(self):
        # type: () -> bool
        return self.__len__() > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        return 0

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
        # type: () -> Attribute | None
        """Get the associated attribute."""
        return None

    @property
    def _frames(self):
        # type: () -> list[float]
        """Get all available frames."""
        return []

    def keys(self):
        # type: () -> list[float]
        """Get the keys."""
        if self._frame is None:
            return self._frames

        if isinstance(self._frame, (float, int)):
            return [frame for frame in self._frames if frame == self._frame]

        if isinstance(self._frame, slice):
            if self._frame.start is None:
                if self._frame.stop is None:
                    validKeys = self._frames
                else:
                    validKeys = [frame for frame in self._frames if frame <= self._frame.stop]
            elif self._frame.stop is None:
                validKeys = [frame for frame in self._frames if self._frame.start <= frame]
            else:
                validKeys = [frame for frame in self._frames if self._frame.start <= frame <= self._frame.stop]
            return [frame for frame in self._frames if frame in validKeys]
        raise TypeError(type(self._frame))

    def values(self):
        # type: () -> list[Attribute]
        """Get the values."""
        return [value for frame, value in self.items()]

    def items(self):
        # type: () -> list[tuple[float, Any]]
        """Get the keys and values."""
        return []


class NodeKeyframes(KeyframeBase):
    __slots__ = ['_node', '_data']

    def __init__(self, node, frame=None):
        # type: (Node | NodeKeyframes, float | slice | None) -> None
        _validateSlice(frame)
        self._data = []  # type: list[AttributeKeyframes]

        if isinstance(node, NodeKeyframes):
            self._node = node.node
            self._data = node._data

        else:
            self._node = node
            currentNode = node

            # Get connections from both the node and its shape
            # This matches the `mc.keyframe` behaviour
            for i in range(2):
                if i:
                    nodeShape = node.shape
                    if nodeShape is None:
                        continue
                    currentNode = nodeShape

                for plug in currentNode.api.dependencyNode.getConnections():
                    for childPlug in utils.getChildPlugs(plug):
                        attr = Attribute(currentNode, childPlug)
                        self._data.append(AttributeKeyframes(attr))

        super(NodeKeyframes, self).__init__(frame)

    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, self.node)

    def __len__(self):
        # type: () -> int
        return sum(map(len, self._data))

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, NodeKeyframes):
            return self._node == other._node and self._frame == other._frame
        return False

    def __contains__(self, frame):
        # type: (float) -> bool
        return any(frame in kf for kf in self._data)

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    @property
    def _frames(self):
        # type: () -> list[float]
        """Get all available keyframe frames."""
        frames = [frame for kf in self._data for frame in kf._keyframes]
        frames.sort()
        return frames

    def items(self):
        # type: () -> list[tuple[float, Attribute]]
        """Get the keyed frames and attributes."""
        valid = self.keys()
        items = [(frame, kf.attr) for kf in self._data for frame in kf._keyframes if frame in valid]
        items.sort()
        return items

    def __iter__(self):
        # type: () -> Iterator[Keyframe]
        """Iterate over each keyframe."""
        valid = self.keys()
        result = (Keyframe(kf.attr, frame) for kf in self._data for frame in kf._keyframes if frame in valid)
        # TODO: Test sorted with non integer frames and fix the type check
        return iter(sorted(result, key=lambda kf: kf.frame))  # type: ignore

    @property
    def attrs(self):
        # type: () -> list[Attribute]
        return [kf.attr for kf in self._data]

    def __getitem__(self, frame):
        # type: (float | slice) -> NodeKeyframes
        """Get everything matching a frame.
        Ints, floats and slices are supported.
        """
        return NodeKeyframes(self, frame)

    def __setitem__(self, frame, value):
        # type: (float | slice, float) -> None
        Keyframe(self.node, frame).set(value)

    def set(self, value=None, **kwargs):
        # type: (float | None, **Any) -> None
        Keyframe(self.node, self._frame).set(value, **kwargs)

    def __delitem__(self, frame):
        # type: (float | slice) -> None
        Keyframe(self.node, frame).delete()

    def delete(self):
        # type: () -> None
        Keyframe(self.node, self._frame).delete()

    def offset(self, value, relative=True):
        # type: (float, bool) -> int
        """Offset the frames."""
        return Keyframe(self.node, self._frame).offset(value, relative=relative)


class AttributeKeyframes(KeyframeBase):
    __slots__ = ['_attr', '_keyframes']

    def __init__(self, attr, frame=None):
        # type: (Attribute | AttributeKeyframes, float | slice | None) -> None
        _validateSlice(frame)
        if isinstance(attr, AttributeKeyframes):
            self._attr = attr.attr
            self._keyframes = attr._keyframes  # type: dict[float, float]

        else:
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

        super(AttributeKeyframes, self).__init__(frame)

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

    @property
    def _frames(self):
        # type: () -> list[float]
        """Get all available keyframe frames."""
        return list(sorted(self._keyframes))

    def items(self):
        # type: () -> list[tuple[float, Any]]
        """Get the keyed frames and values."""
        return [(frame, self._keyframes[frame]) for frame in self.keys()]

    @overload
    def __getitem__(self, frame):
        # type: (float) -> Keyframe
        pass

    @overload
    def __getitem__(self, frame):
        # type: (slice) -> AttributeKeyframes
        pass

    def __getitem__(self, frame):
        # type: (float | slice) -> Keyframe | AttributeKeyframes
        """Get a keyframe."""
        if isinstance(frame, (int, float)):
            return Keyframe(self.attr, frame)
        return AttributeKeyframes(self, frame)

    def __setitem__(self, frame, value):
        # type: (float | slice, float) -> None
        """Set a keyframe."""
        Keyframe(self.attr, frame).set(value)

    def set(self, value=None, **kwargs):
        # type: (float | None, **Any) -> None
        Keyframe(self.attr, self._frame).set(value, **kwargs)

    def __delitem__(self, frame):
        # type: (float | slice) -> None
        """Delete a keyframe."""
        Keyframe(self.attr, frame).delete()

    def delete(self):
        # type: () -> None
        Keyframe(self.attr, self._frame).delete()

    @property
    def locked(self):
        # type: () -> bool
        """Get the locked state of keyframes."""
        ktvPlug = _getKtvPlug(self.attr.api.plug)
        if ktvPlug is None:
            return False
        return ktvPlug.isLocked

    @locked.setter
    def locked(self, value):
        # type: (bool) -> None
        """Lock or unlock the keyframes.

        Raises:
            KeyframeLockError
        """
        utils.logger.info('Setting %s keyframe locked state: %r', self.attr, value)
        ktvPlug = _getKtvPlug(self.attr.api.plug)
        if ktvPlug is None:
            raise exceptions.KeyframeLockError(self.node, self.attr)
        mc.setAttr(ktvPlug.name(), lock=value)

    def lock(self):
        # type: () -> None
        """Lock the keyframes.

        Raises:
            KeyframeLockError
        """
        self.locked = True

    def unlock(self):
        # type: () -> None
        """Unlock the keyframes.

        Raises:
            KeyframeLockError
        """
        self.locked = False

    def offset(self, value, relative=True):
        # type: (float, bool) -> int
        """Offset the frames."""
        return Keyframe(self.attr, self._frame).offset(value, relative=relative)


class Keyframe(KeyframeBase):
    """Keyframe for a specific attribute.
    May be for a single frame or multiple.

    TODO: Change to only accept a single frame.
    """

    __slots__ = ['_node', '_attr']

    def __init__(self, attr, frame=None):
        # type: (Node | Attribute, float | slice | None) -> None
        if TYPE_CHECKING:
            self._attr = None  # type: Attribute | None

        if isinstance(attr, Attribute):
            self._node = attr.node
            self._attr = attr
        elif isinstance(attr, Node):
            self._node = attr
            self._attr = None
        else:
            raise TypeError(type(attr))

        super(Keyframe, self).__init__(frame)

    @property
    def attr(self):
        # type: () -> Attribute | None
        """Get the associated attribute."""
        return self._attr

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    def __repr__(self):
        # type: () -> str
        item = self.attr  # type: Node | Attribute | None
        if item is None:
            item = self.node
        return '{}({!r}, {})'.format(type(self).__name__, item, self.frame)

    def __str__(self):
        # type: () -> str
        item = self.attr  # type: Node | Attribute | None
        if item is None:
            item = self.node
        return '{} ({})'.format(item, self.frame)

    def __len__(self):
        # type: () -> list[int] | int
        # TODO: Fix type check, maybe was set to __len__ by accident
        """Get the number of keyframes."""
        node = self.node
        attr = self.attr
        frame = self.frame

        kwargs = {'query': True, 'keyframeCount': True}  # type: dict[str, Any]
        if attr is not None:
            kwargs['attribute'] = attr.attr

        if not isinstance(frame, slice):
            if frame is not None:
                kwargs['time'] = (frame, frame)
            result = mc.keyframe(node, **kwargs)
            if not result:
                return 0
            return result

        if (frame.step or 1) != 1:
            results = []
            for f in range(frame.start, frame.stop + 1, frame.step):
                result = mc.keyframe(node, time=(f, f), **kwargs)
                if result:
                    results.append(result)
            return results

        return mc.keyframe(nodetime=(frame.start, frame.stop), **kwargs)

    @property
    def frame(self):
        # type: () -> float | slice | None
        """Get the frame value."""
        return self._frame

    @frame.setter
    def frame(self, value):
        # type: (float) -> None
        """Set a new frame value."""
        self.offset(value, relative=False)

    def get(self):
        # type: () -> float | list[float] | None
        """Get a keyframe value."""
        node = self.node
        attr = self.attr
        frame = self.frame

        kwargs = {'query': True, 'valueChange': True}  # type: dict[str, Any]
        if attr is not None:
            kwargs['attribute'] = attr.attr

        results = []
        for time in _toTime(frame):
            result = mc.keyframe(node, time=time, **kwargs)
            if result is not None:
                results.extend(result)
        if isinstance(frame, slice):
            return results
        return results[0] if results else None

    def set(self, value=None, **kwargs):
        # type: (float | None, **Any) -> int
        """Set a keyframe."""
        node = self.node
        attr = self.attr
        frame = self.frame
        utils.logger.info('Setting keyframe on "%s" (frame %s, value %s)',
                          attr if attr is not None else node, frame, value)

        if attr is not None:
            ktvPlug = _getKtvPlug(attr.api.plug)
            if ktvPlug is not None and ktvPlug.isLocked:
                raise exceptions.LockedKeyframeError(attr.node, attr.attr)
            kwargs['attribute'] = attr.attr

        if value is not None:
            kwargs['value'] = value

        count = 0
        for time in _toTime(frame, setKeyframe=True):
            count += mc.setKeyframe(node, time=time, **kwargs)
        return count

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
            ktvPlug = _getKtvPlug(attr.api.plug)
            if ktvPlug is None:
                return 0
            if ktvPlug.isLocked:
                raise exceptions.LockedKeyframeError(attr.node, attr.attr)
            kwargs['attribute'] = attr.attr

        count = 0
        for time in _toTime(frame):
            count += mc.cutKey(node, time=time, **kwargs)
        return count

    def offset(self, value, relative=True):
        # type: (float, bool) -> int
        """Offset the keyframes.
        Note that a keyframe can't be offset past an adjacent keyframe.
        """
        node = self.node
        attr = self.attr
        frame = self.frame

        if frame is None:
            utils.logger.info('Offsetting keyframe on "%s" by %s',
                              attr if attr is not None else node, value)
        else:
            utils.logger.info('Offsetting keyframe on "%s" (frame %s) by %s',
                              attr if attr is not None else node, frame, value)

        kwargs = {'edit': True, 'relative': relative, 'timeChange': value}  # type: dict[str, Any]
        if attr is not None:
            ktvPlug = _getKtvPlug(attr.api.plug)
            if ktvPlug is not None and ktvPlug.isLocked:
                raise exceptions.LockedKeyframeError(attr.node, attr.attr)
            kwargs['attribute'] = attr.attr

        count = 0
        for time in _toTime(frame):
            count += mc.keyframe(node, time=time, **kwargs)
        return count

    @property
    def value(self):
        # type: () -> list[float] | float | None
        """Get a keyframe value."""
        return self.get()

    @value.setter
    def value(self, value):
        # type: (float | None) -> None
        """Set a keyframe."""
        self.set(value)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute
from .node import Node
