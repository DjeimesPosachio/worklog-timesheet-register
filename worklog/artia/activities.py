"""Folders and activities, and the number-to-activity index.

The number written in the spreadsheet is a prefix of the activity *title*, not
its id, so resolving an entry always requires walking the folders once and
indexing by that prefix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from worklog.errors import ArtiaError

_LIST_FOLDERS = """
query ListFolders($accountId: Int!) {
  listingFolders(accountId: $accountId) { id name }
}
"""

_LIST_ACTIVITIES = """
query ListActivities($accountId: Int!, $folderId: Int!) {
  listingActivities(accountId: $accountId, folderId: $folderId) { id title }
}
"""


class Executor(Protocol):
    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        retry_on_failure: bool = True,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Folder:
    id: int
    name: str


@dataclass(frozen=True)
class Activity:
    id: int
    title: str
    folder_id: int
    folder_name: str


def list_folders(client: Executor, account_id: str) -> list[Folder]:
    rows = client.execute(_LIST_FOLDERS, {"accountId": int(account_id)}).get(
        "listingFolders"
    ) or []
    return [Folder(id=int(row["id"]), name=str(row.get("name") or "")) for row in rows]


def list_activities(client: Executor, account_id: str, folder: Folder) -> list[Activity]:
    rows = client.execute(
        _LIST_ACTIVITIES, {"accountId": int(account_id), "folderId": folder.id}
    ).get("listingActivities") or []
    return [
        Activity(
            id=int(row["id"]),
            title=str(row.get("title") or ""),
            folder_id=folder.id,
            folder_name=folder.name,
        )
        for row in rows
    ]


def _all_activities(client: Executor, account_id: str) -> list[Activity]:
    activities: list[Activity] = []
    for folder in list_folders(client, account_id):
        try:
            activities.extend(list_activities(client, account_id, folder))
        except ArtiaError:
            continue
    return activities


def build_index(
    client: Executor, account_id: str, pattern: re.Pattern[str]
) -> dict[str, Activity]:
    index: dict[str, Activity] = {}
    for activity in _all_activities(client, account_id):
        match = pattern.match(activity.title)
        if match:
            index.setdefault(match.group(1), activity)
    return index


def search(client: Executor, account_id: str, term: str) -> list[Activity]:
    needle = term.casefold()
    return [a for a in _all_activities(client, account_id) if needle in a.title.casefold()]
