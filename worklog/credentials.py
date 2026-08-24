"""Artia credentials in the system keyring.

Nothing else in the package touches the keyring: the client receives an email
and a password as plain arguments, so it stays testable without a secret store.
"""

from __future__ import annotations

from dataclasses import dataclass

import keyring

from worklog.errors import ConfigError

SERVICE_NAME = "worklog-timesheet-register"
EMAIL_KEY = "email"


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str


def save(email: str, password: str) -> None:
    keyring.set_password(SERVICE_NAME, EMAIL_KEY, email)
    keyring.set_password(SERVICE_NAME, email, password)


def load() -> Credentials:
    email = keyring.get_password(SERVICE_NAME, EMAIL_KEY)
    password = keyring.get_password(SERVICE_NAME, email) if email else None
    if not email or not password:
        raise ConfigError("Nenhuma credencial guardada. Rode 'apontar login' primeiro.")
    return Credentials(email=email, password=password)


def delete() -> None:
    email = keyring.get_password(SERVICE_NAME, EMAIL_KEY)
    if not email:
        return
    if keyring.get_password(SERVICE_NAME, email) is not None:
        keyring.delete_password(SERVICE_NAME, email)
    keyring.delete_password(SERVICE_NAME, EMAIL_KEY)
