class BaseError(RuntimeError):
    MESSAGE = 'Error'

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super(BaseError, self).__init__(self.MESSAGE.format(**self.kwargs))


class NodeError(BaseError):
    MESSAGE = 'Error: {node}'

    def __init__(self, node, **kwargs):
        super(NodeError, self).__init__(node=node, **kwargs)


class NodeNotFoundError(NodeError):
    MESSAGE = 'No node matches name: {node}'


class NodeDeletedError(NodeNotFoundError):
    MESSAGE = 'Node no longer exists: {node}'


class InvalidNodeError(NodeError):
    MESSAGE = '"{node}" is not valid'


class AttributeNotFoundError(NodeError):
    MESSAGE = 'Attribute not found: {node}.{attr}'

    def __init__(self, node, attr):
        super(AttributeNotFoundError, self).__init__(node, attr=attr)


class AlreadyIsChildError(NodeError):
    MESSAGE = '"{node}" is already a child of "{parent}"'

    def __init__(self, node, parent):
        super(AlreadyIsChildError, self).__init__(node, parent=parent)


class NoBoundingBoxError(NodeError):
    MESSAGE = '"{node}" has no bounding box'
