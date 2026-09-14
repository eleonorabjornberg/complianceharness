---
name: Task
about: A unit of work an agent can finish without asking a question
labels: task
---

## Claim on the world

What can a reviewer see afterwards that they cannot see now?

## Shape

- Files it may create or change:
- Files it must not touch (beyond the human-only paths):
- New collector / new claim / CLI surface / infrastructure:

## Acceptance

- Test that must exist and fail before the change:
- Fixture it builds:
- Status it must be able to produce (SATISFIED / MISSING / STALE / UNVERIFIABLE):

## Failure it must handle

What the collector returns when the thing it looks for is absent, broken,
or not a git repository at all. UNVERIFIABLE is an answer; raising is not.

## Mutation to demonstrate

The wrong version of this change, and the test that should catch it.
