"""Erreurs métier, traduites en statut HTTP en un seul endroit (web.py)."""


class NotFound(LookupError):
    status = 404


class Unauthorized(PermissionError):
    status = 401


class BadRequest(ValueError):
    status = 400


class TooMany(BadRequest):
    status = 429


class Unavailable(BadRequest):
    status = 503
