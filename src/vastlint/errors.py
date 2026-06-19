class VastlintError(Exception):
    """Base class for all vastlint errors."""


class LibraryError(VastlintError):
    """Raised when the native libvastlint cannot be loaded or returns an unexpected value."""
