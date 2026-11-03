"""Projects (SS-026 §4.2)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    CreateProjectRequest,
    ListProjectsQuery,
    Project,
    ProjectItemsAdded,
    ProjectItemsRemoved,
    ProjectItemsRequest,
    ProjectList,
    UpdateProjectRequest,
)
from .._helpers.pagination import paginate


class Projects:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(self, body: CreateProjectRequest, /, **options: Unpack[RequestOptions]) -> Project:
        """`POST /projects`."""
        return cast(Project, self._r.call("createProject", json=body, options=options))

    def list(
        self, query: ListProjectsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> ProjectList:
        """`GET /projects`."""
        return cast(ProjectList, self._r.call("listProjects", query=query, options=options))

    def list_all(
        self, query: ListProjectsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> Iterator[Project]:
        """Every project across pages (lazy; `limit` is the page size)."""
        pages = paginate(lambda q: self.list(cast(ListProjectsQuery, q), **options), query)
        return cast(Iterator[Project], pages)

    def get(self, id: str, /, **options: Unpack[RequestOptions]) -> Project:
        """`GET /projects/{id}`."""
        return cast(Project, self._r.call("getProject", path={"id": id}, options=options))

    def update(
        self, id: str, body: UpdateProjectRequest, /, **options: Unpack[RequestOptions]
    ) -> Project:
        """`PATCH /projects/{id}`."""
        result = self._r.call("updateProject", path={"id": id}, json=body, options=options)
        return cast(Project, result)

    def delete(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /projects/{id}`."""
        self._r.call("deleteProject", path={"id": id}, options=options)

    def add_items(
        self, id: str, body: ProjectItemsRequest, /, **options: Unpack[RequestOptions]
    ) -> ProjectItemsAdded:
        """`POST /projects/{id}/items`."""
        result = self._r.call("addProjectItems", path={"id": id}, json=body, options=options)
        return cast(ProjectItemsAdded, result)

    def remove_items(
        self, id: str, body: ProjectItemsRequest, /, **options: Unpack[RequestOptions]
    ) -> ProjectItemsRemoved:
        """`POST /projects/{id}/items/remove`."""
        result = self._r.call("removeProjectItems", path={"id": id}, json=body, options=options)
        return cast(ProjectItemsRemoved, result)
