import logging

import maya.api.OpenMaya as om2

from . import exceptions
from .types import StrMixin


logger = logging.getLogger(__name__)


class GenerateFnCall(object):
    """Lazily generate the function call text.
    This is intended for use with debug logging so that the expensive
    string operations don't need to be performed for most users.
    """
    __slots__ = ['fn', 'args', 'kwargs']

    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
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
        if isinstance(item, StrMixin):
            item = item.name
        return repr(item)


def runAndLog(fn, *args, **kwargs):
    """Run functions and log them."""
    fnCall = GenerateFnCall(fn, *args, **kwargs)
    logger.debug('%s', fnCall)
    return fn(*args, **kwargs)


def raiseIfNodeNotFound(node):
    """Raise an error if the node doesn't exist."""
    if not node.exists:
        raise exceptions.NodeDeletedError(node)


def unnetworkPlug(plug):
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

    new = om2.MPlug(plug.node(), plug.attribute())
    if plug.isElement:
        return new.elementByLogicalIndex(plug.logicalIndex())
    return new
