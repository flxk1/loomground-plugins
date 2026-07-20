# loomground-kg — the KG cockpit skill

A digest-aware cockpit over the Loomground Versum knowledge graph, and a control surface for
the Loomground skill platforms. `kg_query.py` is the read-only lens into the KG index the
migration wrote to `Loomground Sources/06_Graph/versum/`; `SKILL.md` is the cockpit behavior.

## Install / use
Point it at the KG and run the read tool:
```
KG_ROOT=".../Knowledge/Loomground Sources/06_Graph/versum" \
  python3 skills/loomground-kg/scripts/kg_query.py status
```
Or set `KG_ROOT` once in your environment. The skill grounds every answer on this tool.

## Status
Built: `kg_query.py` (status / urn / search / libraries), verified against the real KG
(53 domains, 2,955 works, ~392k claims, 99.7% reuse). Pending: the concept layer lights up
the model-level both-ways once the coordinate-identity curation runs; digest grounding
deepens once the news/event model links signals to sources.
