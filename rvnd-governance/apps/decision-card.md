# Decision card

Renders the human **confirm** step: the point where a person approves, holds, or denies an item
put to oversight. This is where a loosening earns its signature.

## Source

Built from the oversight surface: the item awaiting sign-off, the lane and rules it touches, and
the identity of the person being asked to decide. A task reserved for a person surfaces here and
cannot run automatically.

## Shows

- The item under decision and the verdict context from the patch card.
- The three discrete outcomes available to the person: **approve**, **hold**, **deny**. No slider,
  no confidence score.
- The named approver's resolved identity and the rationale field they must complete for an
  approval that loosens.
- The autonomy stop or time-based stop that placed the item here, if any.

## Rendering rules

- The person decides; the card records. It never pre-selects an outcome or nudges toward approve.
- An approval that loosens is inert without a rationale — the card enforces the rationale, not as
  decoration but as a gate.
- The decision, once made, routes to `apply` and folds into the signed chain with the approver
  attached. The card shows that the signature will be recorded.
- If the person's identity is unresolved, the decision cannot be taken — no-id wall.
