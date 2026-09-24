"""Claims a privacy reviewer makes about a system that processes personal data.

DRAFT: the rationales below were drafted for Eleonora to rewrite. The
fifth merge gate (FACTORY.md) is a human reading exactly these fields,
and this pack does not pass it until she has.

The expectations come from the GDPR, but a rationale here never rests on
an article number. Each one says who asks for the evidence and what goes
wrong for them when it is absent; the source line says where the
expectation was first written down.

Every claim looks for a heading in a privacy document. That is presence
evidence, the weakest rung, and the report should be read that way: it
says the statement a reviewer asks for can be located, never that the
statement is lawful, complete or true.
"""

from __future__ import annotations

from ..model import BLOCKING, Claim, MATERIAL, Pack

_DOCS = ["PRIVACY.md", "docs/PRIVACY.md", "docs/privacy.md", "README.md"]

PACK = Pack(
    name="privacy",
    version="0.1.0",
    source=(
        "GDPR (Regulation (EU) 2016/679): purpose limitation and storage "
        "limitation (Art. 5), lawfulness (Art. 6), information and rights "
        "(Arts. 12-22), transfers (Chapter V)"
    ),
    claims=(
        Claim(
            id="PR-01",
            text="The purposes for which personal data is processed are stated.",
            severity=BLOCKING,
            collector="section_present",
            params={"candidates": _DOCS, "heading": "Purpose of processing"},
            rationale=(
                "Every other privacy question is asked relative to the purpose. "
                "A reviewer cannot judge whether a field is necessary, a retention "
                "period proportionate or a new use compatible until the original "
                "purpose is written down somewhere that can be quoted back."
            ),
        ),
        Claim(
            id="PR-02",
            text="A legal basis is recorded for each purpose.",
            severity=BLOCKING,
            collector="section_present",
            params={"candidates": _DOCS, "heading": "Legal basis"},
            rationale=(
                "Processing without an identified basis is unlawful however well "
                "it is run, and the basis decides what the data subject can later "
                "demand. A team that cannot name it has usually not chosen one, "
                "and discovers that during a complaint rather than before it."
            ),
        ),
        Claim(
            id="PR-03",
            text="A retention period, or the rule that sets one, is declared.",
            severity=MATERIAL,
            collector="section_present",
            params={"candidates": _DOCS, "heading": "Retention"},
            rationale=(
                "Data kept without an end date grows the damage of every future "
                "breach and every future misuse. An auditor asks for the period "
                "because a period is the only thing a deletion job can be checked "
                "against."
            ),
        ),
        Claim(
            id="PR-04",
            text="The route by which a person exercises their data rights is documented.",
            severity=MATERIAL,
            collector="section_present",
            params={"candidates": _DOCS, "heading": "Data subject rights"},
            rationale=(
                "Access and erasure requests arrive with a deadline attached. If "
                "nobody wrote down who receives them and how the data is found, "
                "the first request becomes an investigation and the deadline is "
                "missed while the route is being invented."
            ),
        ),
        Claim(
            id="PR-05",
            text="Any transfer of personal data outside its jurisdiction names its mechanism.",
            severity=MATERIAL,
            collector="section_present",
            params={"candidates": _DOCS, "heading": "International transfers"},
            rationale=(
                "Hosting, analytics and model providers move data abroad by "
                "default. A reviewer needs the mechanism named, or an explicit "
                "statement that nothing leaves, because a transfer nobody "
                "recorded is one nobody assessed."
            ),
        ),
    ),
)
