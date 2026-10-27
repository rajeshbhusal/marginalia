class NotFoundError(Exception):
    """The requested resource doesn't exist."""


class ConflictError(Exception):
    """The request doesn't fit the resource's current state, e.g. editing a started course."""
