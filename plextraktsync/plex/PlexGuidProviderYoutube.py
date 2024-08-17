from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plextraktsync.plex.PlexGuid import PlexGuid


class PlexGuidProviderYoutube:
    def __init__(self, guid: PlexGuid):
        self.guid = guid

    @property
    def link(self):
        return None

    @property
    def title(self):
        id = self.guid.id
        id = ""
        return f"{self.guid.provider}:{self.guid.type}:{id}"
