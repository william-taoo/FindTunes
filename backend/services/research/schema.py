import hashlib
import json
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

SCHEMA_VERSION = 'v6-relevant-excerpts'
GROUPS = {
    'lyrical_emotions': ('happy/joyful', 'confident', 'sad', 'longing'),
    'musical_characteristics': ('energy', 'brightness', 'tension', 'acoustic texture'),
    'combined_vibe': ('reflective', 'triumphant', 'intimate', 'bittersweet'),
}


class SongIdentity(BaseModel):
    genius_id: str = Field(pattern=r'^\d+$')
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    version: str = Field(default='original', max_length=100)

    def cache_key(self):
        # IDs distinguish different recordings; title/version prevent remixes being merged.
        return hashlib.sha256(json.dumps([SCHEMA_VERSION, self.genius_id,
            self.title.casefold(), self.artist.casefold(), self.version.casefold()]).encode()).hexdigest()


class Source(BaseModel):
    id: str
    url: HttpUrl
    title: str
    text: str = Field(max_length=6000)
    kind: Literal['written_excerpt', 'lyrics']
    timestamp_seconds: float | None = Field(default=None, ge=0)
    identity_verified: bool = False
    retrieved_at: float


class Finding(BaseModel):
    claim: str = Field(min_length=1, max_length=500)
    source_id: str
    quote: str = Field(min_length=1, max_length=500)
    category: Literal['lyrical_emotions', 'musical_characteristics', 'combined_vibe']
    support: Literal['sourced_observation', 'lyrical_interpretation', 'synthesis']


class Decision(BaseModel):
    action: Literal['search', 'finish']
    option: int = Field(default=0, ge=0, le=9)
    reason: str = Field(max_length=300)


class ObservationChoice(BaseModel):
    source_index: int = Field(ge=0, le=7)
    sentence_index: int = Field(ge=0, le=19)
    claim: str = Field(min_length=1, max_length=500)


class ObservationSelection(BaseModel):
    observations: list[ObservationChoice] = Field(default_factory=list, max_length=2)


class SupportCheck(BaseModel):
    supported: bool
    exact_song_version: bool
    reason: str = Field(max_length=300)


class Rating(BaseModel):
    label: str
    level: Literal['low', 'medium', 'high', 'unknown']
    explanation: str = Field(max_length=500)
    finding_ids: list[int] = Field(default_factory=list, max_length=5)


class ProfileDraft(BaseModel):
    lyrical_emotions: list[Rating] = Field(default_factory=list, max_length=4)
    musical_characteristics: list[Rating] = Field(default_factory=list, max_length=4)
    combined_vibe: list[Rating] = Field(default_factory=list, max_length=4)


def unknown_profile():
    return {group: [Rating(label=label, level='unknown', explanation='Evidence unavailable.',
                          finding_ids=[]).model_dump() for label in labels]
            for group, labels in GROUPS.items()}


def identity_matches(song: SongIdentity, source: Source):
    import re
    normalize = lambda s: ' '.join(re.findall(r'\w+', s.casefold()))
    text = normalize(source.title + ' ' + source.text)
    # A discovery heuristic, never enough by itself to accept a finding.
    if normalize(song.title) not in text or normalize(song.artist) not in text:
        return False
    variants = ('remix', 'live', 'acoustic', 'sped up', 'slowed', 'cover')
    if song.version == 'original':
        # Check titles to avoid rejecting a review that mentions another version in passing.
        return not any(re.search(r'\b' + re.escape(v) + r'\b', normalize(source.title)) for v in variants)
    return normalize(song.version) in text
