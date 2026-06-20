---
title: "vastlint on PyPI: in-process VAST validation for Python backends"
published: false
description: "pip install a real VAST XML validator that runs in your process, no subprocess, no network hop, backed by a shared Rust core."
tags: python, adtech, video, opensource
---

## TL;DR

```sh
pip install vastlint
```

```python
import vastlint

result = vastlint.validate(vast_xml)
print(result.valid)            # True / False
print(result.summary.errors)   # 0
print(result.issues)           # [Issue(...), ...]
```

A VAST XML validator that runs in-process, returns structured dataclasses, and shares one Rust core with the CLI, the Go binding, the Ruby gem, the MCP server, and the web validator. No subprocess. No HTTP call to anyone. No Rust toolchain at install time.

## The problem if you do video ad tech in Python

VAST is the IAB standard a video player uses to fetch and track an ad. The trouble is that a broken VAST tag is still well-formed XML. It parses fine. It just does not serve.

- Missing `<Impression>`? You do not get paid for the view.
- `<MediaFile>` over HTTP in a secure context? Blocked.
- A malformed wrapper five hops deep? Dead impression in production.
- VAST 2.0 through 4.3 each moved elements around, so your hand-rolled `lxml` checks rot.
1
None of that throws. You learn about it from a revenue dip, not a traceback. A linter exists to close the gap between "parses" and "is actually valid VAST."

Until now the Python options were: shell out to a binary, call an external service, or maintain your own pile of `lxml` rules forever. All three have a tax.

## What you get

`validate()` takes `str` or `bytes` and returns a `Result`. Everything is a frozen dataclass.

```python
import vastlint

result = vastlint.validate(vast_xml)

if not result.valid:
    for issue in result.issues:
        print(issue.severity, issue.id, issue.message, f"line {issue.line}")

print(result.to_json())
```

Each issue is specific enough to act on:

```json
{
  "id": "VAST-2.0-inline-impression",
  "severity": "error",
  "message": "<InLine> must contain at least one <Impression>",
  "path": "/VAST/Ad[0]/InLine",
  "spec_ref": "IAB VAST 2.0 §2.2.1",
  "line": 4,
  "col": 3
}
```

Rule ID, message, document path, the IAB spec citation, plus line and column. "Your VAST is invalid" helps nobody. "Line 4, your InLine has no Impression, per VAST 2.0 §2.2.1" is a thirty-second fix.

## Why in-process matters

vastlint runs inside your process. Not a subprocess, not a microservice, not a call to vastlint.org.

| Approach | Cost |
| --- | --- |
| Subprocess per request | spawn cost, stdout parsing, lifecycle management, falls over under QPS |
| External validation service | network hop, timeouts, retries, a dependency that can take you down, and you ship every tag off-box |
| Hand-rolled `lxml` | you own the entire IAB spec across six versions, forever |
| In-process binding | call a function, get a dataclass, no hop, no daemon, rules maintained upstream |

The wheel bundles a platform-matched shared library (macOS and Linux, ARM and x86), so `pip install` needs no compiler and no Rust. It wraps the stable `vastlint-ffi` C API behind the same core everything else uses, so the result on your backend matches the web validator byte for byte.

## Drop it into FastAPI

```python
from fastapi import FastAPI
from pydantic import BaseModel
import vastlint

app = FastAPI()


class ValidateRequest(BaseModel):
    xml: str
    wrapper_depth: int = 0
    max_wrapper_depth: int = 5
    rule_overrides: dict[str, str] | None = None


@app.post("/validate")
def validate(req: ValidateRequest):
    result = vastlint.validate(
        req.xml,
        wrapper_depth=req.wrapper_depth,
        max_wrapper_depth=req.max_wrapper_depth,
        rule_overrides=req.rule_overrides,
    )
    return result.to_dict()
```

The result shape is JSON-compatible and stable, so it goes straight to a frontend. `to_dict()` and `to_json()` are on the result. Same story in Flask or a Django admin: it is just a library import.

Things this unlocks:

- Gate creative onboarding before a tag enters your serving path.
- Lint at trafficking time with no new infrastructure.
- Batch-scan stored inventory to find how much is quietly out of spec.

## A deterministic verifier for model and agent harnesses

If you point a language model at "produce a valid VAST tag" (drafting, repair, template fill), you need a checker that is faster than the model, never hallucinates, and returns the same verdict every time. A generated tag can parse fine and still be wrong with no exception to catch it. That is what a linter is, and vastlint returns structured detail, not a vibe, so you can build a real signal.

As a reward function in a training or rejection-sampling loop:

```python
import vastlint

def vast_reward(generated_xml: str) -> float:
    result = vastlint.validate(generated_xml)
    if result.valid:
        return 1.0
    s = result.summary
    return -1.0 * s.errors - 0.25 * s.warnings   # partial credit, not just pass/fail
```

Per-rule detail lets you shape the reward: hard-fail on errors, weight HTTPS heavier than a missing mezzanine, or reward ten errors down to one. Binary valid/invalid throws away signal the validator already computed.

As a verifier in an agent repair loop, the issues are the feedback. Each one has a message, a path, a line, and a spec citation, exactly what a model can read and act on:

```python
def repair_loop(model, broken_xml, max_turns=4):
    xml = broken_xml
    for _ in range(max_turns):
        result = vastlint.validate(xml)
        if result.valid:
            return xml
        feedback = "\n".join(
            f"{i.severity} at {i.path} (line {i.line}): {i.message} [{i.spec_ref}]"
            for i in result.issues
        )
        xml = model.revise(xml, feedback)
    return xml
```

Generate, validate, feed the structured issues back, revise, repeat. The validator is the part of the loop that does not drift.

Same shape works as an eval harness: run a model over a held-out set of dirty tags, score not just how many came out valid but which rules each model gets wrong most. And because validation is in-process and sub-millisecond, you can run thousands of rollouts without the validator becoming the bottleneck. A subprocess or network call per rollout would dominate the loop. A function call does not.

Agent-shaped harness instead of a training loop? The same core is also an MCP server, so an agent can call validation as a tool. Same rules, two ways in.

## Tune severities per environment

```python
result = vastlint.validate(
    vast_xml,
    rule_overrides={
        "VAST-2.0-mediafile-https": "error",
        "VAST-4.1-mezzanine-recommended": "off",
    },
)
```

Map a rule ID to `error`, `warning`, `info`, or `off`. Full catalog at [vastlint.org/docs/rules](https://vastlint.org/docs/rules/), and those IDs are the ones you pass here.

`wrapper_depth` and `max_wrapper_depth` control how far the validator follows wrapper chains.

## The full API

```python
vastlint.validate(xml, *, wrapper_depth=0, max_wrapper_depth=5, rule_overrides=None) -> Result
vastlint.version() -> str
```

`Result` exposes `.version`, `.issues` (list of `Issue`), `.summary` (`Summary`), `.valid`, `.to_dict()`, and `.to_json()`.

## How it ships

Published from GitHub Actions: vendor the platform libraries from the matching `vastlint` release, run the tests, build sdist and wheel, `twine check` the metadata, publish to PyPI with trusted publishing over OIDC. No long-lived token. The wheel you install is the artifact that passed the checks.

## Try it

```sh
pip install vastlint
```

```python
import vastlint
print(vastlint.version())
```

- Web validator: [vastlint.org/validate](https://vastlint.org/validate)
- Rules: [vastlint.org/docs/rules](https://vastlint.org/docs/rules/)
- Source: [github.com/aleksUIX/vastlint-python](https://github.com/aleksUIX/vastlint-python)

If you have a Python ad tech backend and kept putting off VAST validation because every option was bad, it is one pip install and one function call now.
