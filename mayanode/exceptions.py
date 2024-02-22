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


class NodeAttributeError(NodeError):
    MESSAGE = 'Error: {node}.{attr}'

    def __init__(self, node, attr):
        super(NodeAttributeError, self).__init__(node, attr=attr)


class AttributeNotFoundError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" was not found'


class AttributeLockedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is locked and cannot be modified'


class AttributeConnectedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is connected and cannot be modified'


class AlreadyIsChildError(NodeError):
    MESSAGE = '"{node}" is already a child of "{parent}"'

    def __init__(self, node, parent):
        super(AlreadyIsChildError, self).__init__(node, parent=parent)


class NoBoundingBoxError(NodeError):
    MESSAGE = '"{node}" has no bounding box'


class UVSetError(NodeError):
    MESSAGE = 'Error: {node}.uvSet[{uvSet}]'

    def __init__(self, node, uvSet):
        super(UVSetError, self).__init__(node, uvSet=uvSet)


class UVSetDeleteDefaultError(UVSetError):
    MESSAGE = 'The default UV set "{node}.{uvSet}" cannot be deleted.'


class UVSetNotFoundError(UVSetError):
    MESSAGE = 'The UV set "{node}.{uvSet}" was not found'


class ColorSetError(NodeError):
    MESSAGE = 'Error: {node}.colorSet[{colorSet}]'

    def __init__(self, node, colorSet):
        super(ColorSetError, self).__init__(node, colorSet=colorSet)


class ColorSetNotFoundError(ColorSetError):
    MESSAGE = 'The color set "{node}.{colorSet}" was not found'
