"""Claims about a codebase where autonomous agents write the code.

There is no framework to cite here yet, which is the interesting part.
These claims are drawn from the controls that actually fail in practice
when a swarm of coding agents is pointed at a repository: nobody wrote
down what the agents were forbidden to touch, nobody can attribute a
change to the agent that made it, and the tests that were supposed to
catch a cheating agent had no power to catch anything.

The rationale field matters more in this pack than in any other. When
the expectations are not yet written down by a regulator, the argument
for each claim has to stand on its own.
"""

from __future__ import annotations

from ..model import BLOCKING, Claim, MATERIAL, Pack

PACK = Pack(
    name="agent-control",
    version="0.1.0",
    source="No published framework. Controls derived from observed failure modes.",
    claims=(
        Claim(
            id="AC-01",
            text="The boundaries agents may not cross are written down.",
            severity=BLOCKING,
            collector="document_present",
            params={
                "candidates": ["CONTRACT.md", "AGENT_CONTRACT.md", "AGENTS.md"],
                "must_mention": ["human-only"],
            },
            rationale=(
                "An agent that may edit the test that judges it is not being "
                "judged. Every other control in this pack rests on some region of "
                "the repository being outside the agent's reach."
            ),
        ),
        Claim(
            id="AC-02",
            text="Agents are given standing instructions in the repository itself.",
            severity=MATERIAL,
            collector="document_present",
            params={"candidates": ["AGENTS.md", "CLAUDE.md", "CONTRACT.md"]},
            rationale=(
                "Instructions held in one operator's chat history are not a "
                "control: they cannot be reviewed, versioned or inherited by the "
                "next person to run the factory."
            ),
        ),
        Claim(
            id="AC-03",
            text="A reviewer is told what evidence a change must carry before it can be merged.",
            severity=BLOCKING,
            collector="section_present",
            params={
                "candidates": ["CONTRACT.md", "AGENT_CONTRACT.md", "CONTRIBUTING.md"],
                "heading": "What a change must carry",
            },
            rationale=(
                "Review throughput is the binding constraint on autonomous "
                "delivery. If the standard lives in a reviewer's head it cannot be "
                "delegated, and the human becomes the bottleneck the factory was "
                "built to remove."
            ),
        ),
        Claim(
            id="AC-04",
            text="The project states how it knows its own tests can detect a defect.",
            severity=MATERIAL,
            collector="section_present",
            params={
                "candidates": ["CONTRACT.md", "README.md", "docs/TESTING.md"],
                "heading": "Test power",
            },
            rationale=(
                "A passing suite is evidence of nothing until someone has shown "
                "the suite fails when the code is wrong. Under autonomous "
                "delivery this stops being hygiene and becomes the primary "
                "control, because no human reads the diff."
            ),
        ),
        Claim(
            id="AC-05",
            text="Reported results are reproducible from a stated command.",
            severity=MATERIAL,
            collector="document_present",
            params={
                "candidates": ["README.md", "CONTRACT.md"],
                "must_mention": ["reproduce"],
            },
            rationale=(
                "An agent's summary of what it did is a claim by an interested "
                "party. The command that regenerates the artifact is the check on "
                "it."
            ),
        ),
    ),
)
