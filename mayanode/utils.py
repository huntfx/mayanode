import logging

import maya.api.OpenMaya as om2  # type: ignore

from . import exceptions
from .type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable
    from .core.node import Node


logger = logging.getLogger(__name__)


class GenerateFnCall(object):
    """Lazily generate the function call text.
    This is intended for use with debug logging so that the expensive
    string operations don't need to be performed for most users.
    """
    __slots__ = ['fn', 'args', 'kwargs']

    def __init__(self, fn, *args, **kwargs):
        # type: (Callable, *Any, **Any) -> None
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        # type: () -> str
        module = self.fn.__module__
        if module == 'maya.cmds':
            module = 'mc'
        elif module == 'pymel.core':
            module = 'pm'
        args = map(self.repr, self.args)
        kwargs = ('{}={}'.format(k, self.repr(v)) for k, v in self.kwargs.items())
        params = ', '.join(list(args) + list(kwargs))
        return '{}.{}({})'.format(module, self.fn.__name__, params)

    def repr(self, item):
        # type: (Any) -> str
        if isinstance(item, StrMixin):
            item = item.name
        return repr(item)


def runAndLog(fn, *args, **kwargs):
    # type: (Callable, *Any, **Any) -> Any
    """Run functions and log them."""
    fnCall = GenerateFnCall(fn, *args, **kwargs)
    logger.debug('%s', fnCall)
    return fn(*args, **kwargs)


def raiseIfNodeNotFound(node):
    # type: (Node) -> None
    """Raise an error if the node doesn't exist."""
    if not node.exists:
        if not node.api.object.isNull:
            raise exceptions.NullMObjectError
        raise exceptions.NodeDeletedError(node)


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
    if plug.isElement:
        return new.elementByLogicalIndex(plug.logicalIndex())

    return new


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .types import StrMixin
