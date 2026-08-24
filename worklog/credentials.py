"""Artia credentials in the system keyring.

Nothing else in the package touches the keyring: the client receives an email
and a password as plain arguments, so it stays testable without a secret store.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import keyring
from keyring.errors import KeyringError

from worklog.errors import ConfigError

SERVICE_NAME = "worklog-timesheet-register"
EMAIL_KEY = "email"


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str = field(repr=False)


def _unavailable(error: KeyringError) -> ConfigError:
    return ConfigError(
        "Não foi possível acessar o keyring do sistema.", detail=str(error)
    )


def _forget(email: str) -> None:
    if keyring.get_password(SERVICE_NAME, email) is not None:
        keyring.delete_password(SERVICE_NAME, email)


def save(email: str, password: str) -> None:
    try:
        previous = keyring.get_password(SERVICE_NAME, EMAIL_KEY)
        if previous and previous != email:
            _forget(previous)
        keyring.set_password(SERVICE_NAME, EMAIL_KEY, email)
        keyring.set_password(SERVICE_NAME, email, password)
    except KeyringError as exc:
        raise _unavailable(exc) from exc


def load() -> Credentials:
    try:
        email = keyring.get_password(SERVICE_NAME, EMAIL_KEY)
        password = keyring.get_password(SERVICE_NAME, email) if email else None
    except KeyringError as exc:
        raise _unavailable(exc) from exc
    if not email or not password:
        raise ConfigError("Nenhuma credencial guardada. Rode 'apontar login' primeiro.")
    return Credentials(email=email, password=password)


def delete() -> None:
    try:
        email = keyring.get_password(SERVICE_NAME, EMAIL_KEY)
        if not email:
            return
        _forget(email)
        keyring.delete_password(SERVICE_NAME, EMAIL_KEY)
    except KeyringError as exc:
        raise _unavailable(exc) from exc
