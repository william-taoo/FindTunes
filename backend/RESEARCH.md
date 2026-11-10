# Song vibe descriptions

`GET /recommend/stream?song_name=Bad%20Habit&artist_name=Steve%20Lacy`
returns lyric-based Pinecone recommendations immediately, then attaches a
background job for short vibe descriptions. Poll `GET /research/jobs/{id}`.
Vibe lookup enriches the cards; it does not rerank the lyric matches.

## Default: one search and one description per song

The default `research_mode=vibe` looks up the input song and up to three
recommendations. Each song gets at most one Brave request and one short,
plain-prose local-model generation. No search retries, structured extraction,
ratings, claim judges, JSON repair, or separate synthesis calls run in this flow.
The older `deep` mode name is accepted as an alias for `vibe`.

The input song gets a general description of mood, atmosphere, energy, vocals,
or production. Each candidate description uses its own search excerpts and the
input song's completed vibe as context, describing the candidate's overall feel
and a natural similarity or difference. The model is instructed not to force a
match. If the input song's description is unavailable, candidate descriptions
can still describe their own vibe without claiming a comparison.

Searches overlap across all songs. Candidates wait for input-song context before
joining the local generation queue. There is one shared inference gate and a
four-call job budget: one generation per song, no extra lyric explanation calls.
The existing local model lock still serializes actual inference.

The frontend enables AI vibes by default. Cards display the candidate's vibe
paragraph directly; the input vibe appears above the results. Details show
both descriptions and expandable source excerpts. These are source-informed AI
interpretations, not verified musical measurements or direct audio analysis.
There are no musical-rating grids or observation-approval checklists.

## Sources, failure, and storage

The fixed query requests the exact song/artist/version plus general vibe, mood,
atmosphere, and sound reviews. Basic identity/relevance filters remove clearly
unrelated results, artist chart biographies, and generic musical-metric
definitions. General mood/atmosphere descriptions are eligible context. The
model summarizes bounded search snippets, not complete webpages or audio.
Source text is treated as untrusted data, never instructions.

No-source and technical-failure cases remain possible. They are not displayed as
failed evidence checks: the UI simply says the vibe description is unavailable
and retains any retrieved excerpts. It never fabricates a vibe when lookup
returns no useful context. Model output is plain prose with only nonempty-output
and length handling; no second model judges it. This reduces latency and brittle
schema failures, but means the prose is not independently verified.

`research_mode=quick` skips AI generation and returns excerpts plus the existing
full-song lexical overlap. Source-only quick results are not vibe descriptions.
The standalone legacy `/recommend` endpoint retains its older lyric explanations;
the interactive streaming flow no longer generates those explanations.

Research profiles and comparisons are not cached. Existing cache utilities,
migrations, and historical rows are unused by this flow. Jobs stay in memory
for 30 minutes for polling, and local JSONL traces remain in
`backend/.research-traces/{job-id}.jsonl`. These are lifecycle/diagnostic records,
not reusable research caches. No full lyrics are persisted by this flow.

## Configuration and limits

Configure `backend/.env` from `.env.example`. `BRAVE_SEARCH_API_KEY` enables
written lookup; `LOCAL_LLM_MODEL` and `LOCAL_LLM_DEVICE` configure existing local
inference. No hosted fallback or automatic model download is used.
`RESEARCH_ENABLED` enables background lookup.

`RESEARCH_JOB_SECONDS` is clamped to 120 seconds and
`RESEARCH_SONG_SECONDS` to 60 seconds for vibe mode. Quick mode retains its
60-second job and 15-second per-song limits. Each prose call has a 25-second
absolute deadline including queue wait, up to 15 seconds of generation, and a
160-token output limit. Actual performance depends on hardware and source I/O.
Native model operations may outlive cancellation, but canceled jobs do not publish
late results. One vibe job or two quick jobs can run concurrently. Multi-worker
deployment still needs a durable/shared job store before scaling.

`/research/config` reports default mode `vibe`, one model call per song, zero
support-check calls, disabled caching, and revision `v10-simple-vibe`.
Profiles add `vibe`, `compares_to_seed`, and `vibe_basis=search_excerpts`.
Candidate results expose the card-ready paragraph as `vibe_description`.
Legacy profile/findings fields remain empty/unknown for compatibility.
Outcomes are `searching`, `analyzing`, `vibe_ready`, `sources_only`, `no_sources`,
`analysis_failed`, or `search_failed`. Timing/error traces omit secrets and raw
source payloads. Restarting the backend clears in-memory job IDs.

## Verification

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
backend/.venv/Scripts/python.exe backend/scripts/check_research.py --model --live
```

From `frontend`, run `npm run test:research` and
`node_modules/.bin/tsc --noEmit --incremental false`.

Offline tests cover one search/one prose generation, no support-check or lyric
model calls, input-vibe propagation, parallel source lookup, missing input
context, source-only mode, source preservation on failure, and deadlines.
Live checks are explicit and consume provider quota.
