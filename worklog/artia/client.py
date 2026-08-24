"""GraphQL transport for the Artia API.

Authenticates with the undocumented ``authenticationByEmail`` mutation, which
returns the same ``Auth`` type as the documented client-credentials one but
needs no organization admin. Every authenticated request carries the
``organizationId`` header; without it the API answers "Organização não
encontrada" regardless of the query.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from worklog.errors import ArtiaError

DEFAULT_API = "https://api.artia.com/graphql"
BACKOFFS = (0.5, 1.0, 2.0)
PACING_SECONDS = 0.15

_AUTHENTICATE = """
mutation AuthenticationByEmail($email: String!, $password: String!) {
  authenticationByEmail(email: $email, password: $password) { token }
}
"""


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ArtiaError("A URL da API do Artia precisa usar HTTP ou HTTPS.")
    if not parsed.hostname:
        raise ArtiaError("A URL da API do Artia precisa incluir um host.")
    return base_url.rstrip("/")


class ArtiaClient:
    def __init__(
        self,
        email: str,
        password: str,
        organization_id: str,
        base_url: str = DEFAULT_API,
        timeout: float = 30.0,
    ) -> None:
        if not (email and password):
            raise ArtiaError("E-mail e senha do Artia são obrigatórios.")
        self.base_url = _validate_base_url(base_url or DEFAULT_API)
        self._email = email
        self._password = password
        self._organization_id = organization_id
        self._timeout = timeout
        self._token: str | None = None
        self._last_request = 0.0
        self._http = httpx.Client(timeout=httpx.Timeout(timeout))

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < PACING_SECONDS:
            time.sleep(PACING_SECONDS - elapsed)
        self._last_request = time.monotonic()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ArtiaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._token is None:
            self._authenticate()
        return self._send(query, variables, authenticated=True, allow_renew=True)

    def _authenticate(self) -> None:
        data = self._send(
            _AUTHENTICATE,
            {"email": self._email, "password": self._password},
            authenticated=False,
            allow_renew=False,
        )
        token = (data.get("authenticationByEmail") or {}).get("token")
        if not token:
            raise ArtiaError("O Artia não devolveu um token de autenticação.")
        self._token = str(token)

    def _headers(self, authenticated: bool) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"
            if self._organization_id:
                headers["organizationId"] = self._organization_id
        return headers

    def _send(
        self,
        query: str,
        variables: dict[str, Any] | None,
        *,
        authenticated: bool,
        allow_renew: bool,
    ) -> dict[str, Any]:
        attempt = 0
        renewed = False
        while True:
            self._pace()
            try:
                response = self._http.post(
                    self.base_url,
                    headers=self._headers(authenticated),
                    json={"query": query, "variables": variables or {}},
                )
            except httpx.HTTPError as exc:
                if attempt < len(BACKOFFS):
                    time.sleep(BACKOFFS[attempt])
                    attempt += 1
                    continue
                raise ArtiaError("Falha de rede ao acessar o Artia.", detail=str(exc))

            if response.status_code == 401 and allow_renew and not renewed:
                self._token = None
                self._authenticate()
                renewed = True
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < len(BACKOFFS):
                    time.sleep(BACKOFFS[attempt])
                    attempt += 1
                    continue

            if response.status_code >= 400:
                raise self._status_error(response.status_code)

            body = response.json()
            errors = body.get("errors")
            if errors:
                message = str(errors[0].get("message", "Erro do Artia."))
                raise ArtiaError(message, status=response.status_code)
            return body.get("data") or {}

    @staticmethod
    def _status_error(status: int) -> ArtiaError:
        if status == 401:
            return ArtiaError("Credencial do Artia inválida. Rode 'apontar login'.", status=status)
        if status == 403:
            return ArtiaError("Sem permissão para essa ação no Artia.", status=status)
        if status == 404:
            return ArtiaError("Recurso não encontrado no Artia.", status=status)
        if status == 429:
            return ArtiaError("Limite de requisições do Artia atingido.", status=status)
        return ArtiaError(f"O Artia respondeu HTTP {status}.", status=status)
