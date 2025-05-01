"""Custom exceptions for the module."""

import sys

from . import constants


if sys.version_info.major < 3:
    # pylint: disable=redefined-builtin
    class FileNotFoundError(OSError):
        """File not found."""


class BaseError(RuntimeError):
    MESSAGE = 'Error'

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super(BaseError, self).__init__(self.MESSAGE.format(**self.kwargs))


class NullMObjectError(BaseError, TypeError):
    MESSAGE = 'This object is null'


class NodeError(BaseError):
    MESSAGE = 'Error: {node}'

    def __init__(self, node, **kwargs):
        super(NodeError, self).__init__(node=node, **kwargs)


class NodeNotFoundError(NodeError):
    MESSAGE = 'No node matches name: {node}'


class NodeDeletedError(NodeNotFoundError):
    MESSAGE = 'Node no longer exists{node}'

    def __init__(self, node=None, **kwargs):
        if node is None:
            node = ''
        else:
            node = ': ' + node
        super(NodeDeletedError, self).__init__(node=node, **kwargs)


class InvalidNodeError(NodeError):
    MESSAGE = '"{node}" is not valid'


class NotADagNodeError(NodeError):
    MESSAGE = '"{node}" is not a DAG node'


class NotACameraError(NodeError):
    MESSAGE = '"{node}" is not a camera'


class ReadOnlyNodeError(NodeError):
    MESSAGE = '"{node}" is read only'


class RenameReadOnlyNodeError(ReadOnlyNodeError):
    MESSAGE = 'Cannot rename "{node}" as it is read only'


class RenameReferencedNodeError(ReadOnlyNodeError):
    MESSAGE = 'Cannot rename "{node}" as it is from a reference'


class RenameLockedNodeError(ReadOnlyNodeError):
    MESSAGE = 'Cannot rename "{node}" as it is locked'


class NodeAttributeError(NodeError):
    MESSAGE = 'Error: {node}.{attr}'

    def __init__(self, node, attr, **kwargs):
        super(NodeAttributeError, self).__init__(node, attr=attr, **kwargs)


class AttributeNotFoundError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" was not found'


class AttributeLockedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is locked and cannot be modified'


class AttributeConnectedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is connected and cannot be modified'


class ConnectToSelfError(NodeAttributeError):
    MESSAGE = 'Cannot connect attribute "{node}.{attr}" to itself.'


class InvalidAttributeTypeError(NodeAttributeError):
    MESSAGE = 'The value for the attribute "{node}.{attr}" could not be retrieved.'


class AttributOutOfRangeError(NodeAttributeError):
    def __init__(self, node, attr, value, **kwargs):
        super(AttributOutOfRangeError, self).__init__(node, attr, value=value, **kwargs)


class AttributeTooLowError(AttributOutOfRangeError):
    MESSAGE = 'Cannot set the attribute "{node}.{attr}" below its minimum value of {value}.'


class AttributeTooHighError(AttributOutOfRangeError):
    MESSAGE = 'Cannot set the attribute "{node}.{attr}" above its maximum value of {value}.'


class AttributeNotAChildError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is not a child.'


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


class UVSetExistsError(UVSetError):
    MESSAGE = 'Cannot rename "{node}.{uvSet}" to an existing UV set name.'


class ColorSetError(NodeError):
    MESSAGE = 'Error: {node}.colorSet[{colorSet}]'

    def __init__(self, node, colorSet):
        super(ColorSetError, self).__init__(node, colorSet=colorSet)


class ColorSetNotFoundError(ColorSetError):
    MESSAGE = 'The color set "{node}.{colorSet}" was not found'


class ZeroTexelDensityError(BaseError):
    MESSAGE = 'The texel density for "{faces}" is zero and cannot be updated.'

    def __init__(self, faces):
        super(ZeroTexelDensityError, self).__init__(faces=', '.join(faces))


class NamespaceError(BaseError):
    MESSAGE = 'Error: {namespace}'

    def __init__(self, namespace, **kwargs):
        super(NamespaceError, self).__init__(namespace=namespace, **kwargs)


class NamespaceInvalidNameError(NamespaceError):
    MESSAGE = 'The new name for "{namespace}" contains only illegal characters.'


class NamespaceNotFoundError(NamespaceError):
    MESSAGE = 'No namespace matches name: {namespace}'


class NamespaceNotEmptyError(NamespaceError):
    MESSAGE = 'The namespace "{namespace}" is not empty.'


class NamespaceNotUniqueError(NamespaceError):
    MESSAGE = 'Namespace name is not unique: {namespace}'


class NamespaceParentError(NamespaceError):
    MESSAGE = 'Namespace "{namespace}" cannot be parented a child of itself'


class InvalidUuidError(BaseError):
    MESSAGE = '"{uuid}" is not a valid UUID'

    def __init__(self, uuid, **kwargs):
        super(InvalidUuidError, self).__init__(uuid=uuid, **kwargs)


class InvalidTimeUnitError(BaseError):
    MESSAGE = '"{unit}" is not a valid time unit'

    def __init__(self, unit, **kwargs):
        super(InvalidTimeUnitError, self).__init__(unit=unit, **kwargs)

    @property
    def allowed(self):
        # type: () -> list[str]
        """Get the allowed time units.."""
        return list(constants.TIME_UNITS)


class RequiresInteractiveError(BaseError):
    MESSAGE = 'this operation is not supported in batch mode'


class ReferenceError(BaseError):
    MESSAGE = 'error with reference "{reference}"'

    def __init__(self, reference, **kwargs):
        super(ReferenceError, self).__init__(reference=reference, **kwargs)


class ReferenceImportError(ReferenceError):
    MESSAGE = '"{reference}" cannot be imported'


class NotATopLevelReferenceImportError(ReferenceImportError):
    MESSAGE = '"{reference}" cannot be imported as it is not a top level reference'


class UnloadedReferenceImportError(ReferenceImportError):
    MESSAGE = '"{reference}" cannot be imported as it is unloaded'


class ReferenceNamespaceError(ReferenceError):
    MESSAGE = '"{reference}" namespace cannot be edited'


class UnloadedReferenceNamespaceError(ReferenceError):
    MESSAGE = '"{reference}" is unloaded so the namespace cannot be edited'


class ReferenceWithoutNamespaceError(ReferenceError):
    MESSAGE = '"{reference}" was not created using namespaces so the namespace cannot be edited'


class FileInfoError(BaseError):
    MESSAGE = 'error with fileInfo'


class ReadOnlyFileInfoError(FileInfoError):
    MESSAGE = 'fileInfo {reason} and cannot be edited'

    def __init__(self, reason, **kwargs):
        super(ReadOnlyFileInfoError, self).__init__(reason=reason, **kwargs)


class MultipleFileInfoResultsError(FileInfoError):
    MESSAGE = 'more than one fileInfo value returned for "{key}"'

    def __init__(self, key, **kwargs):
        super(MultipleFileInfoResultsError, self).__init__(key=key, **kwargs)


class FileExtensionError(BaseError):
    MESSAGE = 'unexpected file extension (expected "ma" or "mb", got "{ext}")'

    def __init__(self, ext, **kwargs):
        super(FileExtensionError, self).__init__(ext=ext, **kwargs)


class KeyframeError(NodeAttributeError):
    MESSAGE = 'Error with keyframe on "{node}.{attr}".'


class LockedKeyframeError(KeyframeError):
    MESSAGE = 'The keyframe on "{node}.{attr}" is locked and cannot be edited.'


class KeyframeLockError(KeyframeError):
    MESSAGE = '"{node}.{attr}" has no attached curves so it cannot be locked.'


class ViewportError(BaseError):
    MESSAGE = 'Viewport error.'


class InvalidViewportError(ViewportError):
    MESSAGE = 'No valid viewport found.'


class ViewportDeletedError(ViewportError):
    MESSAGE = 'The viewport has been deleted.'
