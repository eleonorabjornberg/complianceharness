"""Claims a model validator or a conformity reviewer would ask for.

Drawn from two overlapping sources: the technical documentation expected
of a high-risk AI system under Annex IV of the EU AI Act, and the model
documentation expected under supervisory model-risk guidance (SR 11-7
and its descendants). They overlap more than the literature admits: both
ask who this is for, what it was built from, how you know it works, and
what you know it cannot do.

Every claim carries the rationale in the reviewer's own terms. A claim
whose rationale is "because the framework says so" is a checklist item
and does not belong here.
"""

from __future__ import annotations

from ..model import ADVISORY, BLOCKING, Claim, FRESH, MATERIAL, Pack

# How many commits a limitations or evaluation section may fall behind HEAD
# before the claim is STALE (P3). A placeholder for Eleonora to set: the
# right number depends on how often a subject commits, and is a judgement
# about the reviewer's tolerance, not a fact about git.
DOCS_MAY_LAG_BY = 20

PACK = Pack(
    name="model-evidence",
    version="0.2.0",
    source="EU AI Act Annex IV; supervisory model-risk guidance (SR 11-7 lineage)",
    claims=(
        Claim(
            id="ME-01",
            text="The intended purpose of the system is written down.",
            severity=BLOCKING,
            collector="document_present",
            params={
                "candidates": ["README.md", "docs/README.md", "MODEL_CARD.md"],
                "must_mention": ["purpose"],
            },
            rationale=(
                "Scope is the first question in every review. Without a stated "
                "purpose there is no standard against which misuse, drift or "
                "out-of-scope deployment can be judged."
            ),
        ),
        Claim(
            id="ME-02",
            text="Data sources are declared with their provenance.",
            severity=BLOCKING,
            collector="document_present",
            params={
                "candidates": ["DATA.md", "docs/DATA.md", "docs/data.md"],
                "must_mention": ["source"],
            },
            rationale=(
                "A model's claims inherit the weaknesses of its inputs. A reviewer "
                "who cannot trace a column back to a publisher and a retrieval date "
                "cannot assess anything downstream of it."
            ),
        ),
        Claim(
            id="ME-03",
            text="Known limitations are recorded.",
            severity=MATERIAL,
            collector="documented_within",
            params={
                "candidates": ["README.md", "MODEL_CARD.md", "docs/LIMITATIONS.md"],
                "heading": "Limitations",
                "within": DOCS_MAY_LAG_BY,
            },
            requires=FRESH,
            rationale=(
                "Undocumented limitations become the user's problem. This is also "
                "the single best proxy for whether the team has actually "
                "interrogated its own work."
            ),
        ),
        Claim(
            id="ME-04",
            text="The evaluation method is documented, including how the test data was held out.",
            severity=BLOCKING,
            collector="documented_within",
            params={
                "candidates": ["README.md", "docs/EVALUATION.md", "PLAN.md"],
                "heading": "Evaluation",
                "within": DOCS_MAY_LAG_BY,
            },
            requires=FRESH,
            rationale=(
                "A performance number without its evaluation design is not "
                "evidence. Look-ahead leakage is the most common defect in "
                "time-series model validation and it is invisible in the headline "
                "metric."
            ),
        ),
        Claim(
            id="ME-05",
            text="A reader is told the command that reproduces the reported results.",
            severity=MATERIAL,
            collector="document_present",
            params={
                "candidates": ["README.md", "docs/README.md"],
                "must_mention": ["reproduce"],
            },
            rationale=(
                "Reproducibility is the difference between a claim and a result. "
                "It is also the cheapest thing on this list to satisfy, which makes "
                "its absence informative."
            ),
        ),
        Claim(
            id="ME-06",
            text="A human owner is named for the system.",
            severity=ADVISORY,
            collector="document_present",
            params={
                "candidates": ["README.md", "OWNERS.md", "CODEOWNERS"],
                "must_mention": ["owner"],
            },
            rationale=(
                "Accountability that is not assigned to a person is not assigned. "
                "Advisory rather than blocking because small projects legitimately "
                "carry this in the repository metadata instead."
            ),
        ),
    ),
)
