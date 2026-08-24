"""Local configuration, kept outside the repository.

Account ids, bucket ids and the spreadsheet path are deployment-specific, so
they never live in version control. Credentials are not here either — those
belong to the system keyring.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from worklog.errors import ConfigError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "worklog-timesheet-register" / "config.toml"
REQUIRED_BUCKETS = ("zamp", "meetings", "tests")


@dataclass(frozen=True)
class ArtiaConfig:
    organization_id: str
    account_id: str
    time_entry_status_id: int


@dataclass(frozen=True)
class Config:
    spreadsheet: Path
    task_pattern: re.Pattern[str]
    artia: ArtiaConfig
    buckets: dict[str, int]


def _require(table: dict, key: str, where: str) -> object:
    if key not in table:
        raise ConfigError(f"Configuração incompleta: falta '{key}' em {where}.")
    return table[key]


def load_config(path: Path | None = None) -> Config:
    target = path or DEFAULT_CONFIG_PATH
    if not target.is_file():
        raise ConfigError(
            f"Configuração não encontrada em {target}. "
            "Crie o arquivo com spreadsheet, task_pattern, [artia] e [buckets]."
        )

    try:
        raw = tomllib.loads(target.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Configuração inválida em {target}.", detail=str(exc)
        ) from exc

    artia_table = _require(raw, "artia", "a raiz")
    buckets_table = _require(raw, "buckets", "a raiz")
    if not isinstance(artia_table, dict) or not isinstance(buckets_table, dict):
        raise ConfigError("As seções [artia] e [buckets] precisam ser tabelas.")

    buckets: dict[str, int] = {}
    for name in REQUIRED_BUCKETS:
        buckets[name] = int(_require(buckets_table, name, "[buckets]"))

    pattern_text = str(_require(raw, "task_pattern", "a raiz"))
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise ConfigError(
            "task_pattern não é uma expressão regular válida.", detail=str(exc)
        ) from exc
    if pattern.groups < 2:
        raise ConfigError(
            "task_pattern precisa de dois grupos: o número da atividade e a descrição."
        )

    return Config(
        spreadsheet=Path(str(_require(raw, "spreadsheet", "a raiz"))).expanduser(),
        task_pattern=pattern,
        artia=ArtiaConfig(
            organization_id=str(_require(artia_table, "organization_id", "[artia]")),
            account_id=str(_require(artia_table, "account_id", "[artia]")),
            time_entry_status_id=int(
                _require(artia_table, "time_entry_status_id", "[artia]")
            ),
        ),
        buckets=buckets,
    )
