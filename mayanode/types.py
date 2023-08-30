from __future__ import absolute_import

from collections import namedtuple


Coordinate = namedtuple('Coordinate', ['x', 'y', 'z'])


class StrMixin(object):  # pylint: disable=useless-object-inheritance
    """Add methods to make the classes behave like strings."""

    __slots__ = []

    def __str__(self):
        return self.name

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    def __contains__(self, value):
        return self.name.__contains__(value)

    def split(self, *args, **kwargs):
        return self.name.split(*args, **kwargs)

    def rsplit(self, *args, **kwargs):
        return self.name.rsplit(*args, **kwargs)
