# vastlint is now on PyPI: VAST validation for your Python backend

If you run a DSP, an SSP, an ad server, or any kind of video trafficking pipeline, you have almost certainly written code that tries to make sense of VAST XML. And if you have written that code in Python, you know the options have been thin. You either shell out to a binary, call an external service over HTTP, or hand-roll a pile of `lxml` checks that drift out of sync with the spec every time IAB ships a new version.

That changes today. `vastlint` is now available as a Python package on PyPI:

```sh
pip install vastlint
```

This post is about what it is, why it exists in this particular shape, and why putting a real VAST validator in-process matters for Python ad tech backends.

## A quick refresher on why VAST validation is hard

VAST (Video Ad Serving Template) is the IAB standard that tells a video player how to fetch, render, and track an ad. It sounds simple, and the happy path is. The problem is everything around the happy path.

VAST has shipped in versions 2.0, 3.0, 4.0, 4.1, 4.2, and 4.3, and each one added, moved, or deprecated elements. Wrappers can chain to other wrappers, which chain to other wrappers, and a malformed tag five hops deep will break a real impression in production. A `MediaFile` served over HTTP instead of HTTPS will get blocked in a secure context. A missing `Impression` node means you never get paid for the view. An `InLine` ad with no `Creatives` is just a broken ad that looks fine until a player chokes on it.

The catch is that none of this throws an exception. A VAST tag that violates the spec is still well-formed XML. It parses cleanly. It just does not work, and you find out from a revenue dip or an angry buyer, not from a stack trace. That gap between "parses" and "is actually valid VAST" is exactly what a linter exists to close.

## What vastlint actually is

vastlint is a VAST XML validator built around a single Rust core. That core is wrapped and shipped in a lot of forms: a CLI, a Go binding, a Ruby gem, an Erlang NIF, an MCP server for AI agents, and the web validator at vastlint.org/validate. The new Python package is another binding onto that same engine.

The important word there is "same." Every one of those surfaces runs the identical rule set against your XML. The result you get from the Python package on your backend matches what you would see in the web validator, what your Go service sees, and what a teammate sees from the CLI. There is one source of truth for what counts as a valid VAST tag, and every language just borrows it.

For Python specifically, the package wraps the stable `vastlint-ffi` C API. You do not need a Rust toolchain, a compiler, or a network connection to use it. The wheel bundles a platform-matched shared library for macOS and Linux on both ARM and x86, so `pip install vastlint` gives you a working validator with zero native build step.

## The basic usage

```python
import vastlint

result = vastlint.validate(vast_xml)

if result.valid:
    print("clean tag")
else:
    print(result.summary.errors)
    print(result.issues[0].message)

print(result.to_json())
```

`validate` takes a `str` or `bytes` and returns a `Result`. The `Result` carries the detected VAST version, a list of issues, a summary count, and a boolean `valid`. Every type is a frozen dataclass, so you can pass them around without worrying about something mutating your validation output halfway through a request.

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

You get the rule ID, a human-readable message, the exact path in the document, a citation back to the IAB spec, and the line and column. That last part matters more than it looks. "Your VAST is invalid" is useless to a buyer. "Line 4, column 3, your InLine ad has no Impression, per IAB VAST 2.0 section 2.2.1" is something a person can fix in thirty seconds.

## Why in-process is the whole point

Here is the design decision that makes this worth writing about. vastlint for Python runs inside your process. It is not a subprocess. It is not a microservice. It is not an HTTP call to vastlint.org.

For a backend that validates VAST, those three alternatives all have a tax:

A subprocess means you are spawning a binary per request, parsing its stdout, managing its lifecycle, and eating process startup cost on a hot path. Under real QPS that falls over.

An external service means a network hop, a timeout policy, a retry policy, a circuit breaker, and a dependency that can take your validation path down even when your own service is healthy. You also ship every tag you validate to someone else's machine, which is a non-starter for a lot of trafficking pipelines.

Hand-rolled `lxml` checks mean you own the entire IAB spec forever, across six VAST versions, and your rules silently rot every time the standard moves.

In-process bindings sidestep all of it. The validation happens in the same memory space as your request handler. There is no hop, no daemon to babysit, no startup cost per call, and the rule coverage is maintained upstream by the shared Rust core. You call a function and you get a dataclass back. That is the whole interaction.

## Where this fits in a real backend

The natural home for this is the validation endpoint that sits between whoever is uploading or trafficking a tag and the rest of your system. Here is a FastAPI handler:

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

The response shape is JSON-compatible and stable, so it goes straight back to a frontend without a translation layer. `to_dict()` and `to_json()` are right there on the result.

A few practical patterns this enables:

You can gate creative onboarding. When a buyer uploads a tag, validate it before it ever enters your ad serving path, and hand them back the exact line and rule that failed so they fix it themselves instead of filing a ticket.

You can lint at trafficking time inside an existing Django or Flask admin, with no new infrastructure, because the validator is just a library import.

You can run it in batch over a backlog of stored tags to find out how much of your existing inventory is quietly out of spec, without standing up anything new.

## Tuning the rules to your environment

Not every shop wants the same severity for every rule. A publisher in a fully HTTPS environment might want HTTP media files to be a hard error. Someone else might not care about the VAST 4.1 mezzanine recommendation and want it silenced. `rule_overrides` handles that:

```python
result = vastlint.validate(
    vast_xml,
    rule_overrides={
        "VAST-2.0-mediafile-https": "error",
        "VAST-4.1-mezzanine-recommended": "off",
    },
)
```

You map a rule ID to `error`, `warning`, `info`, or `off`. The full rule reference lives at vastlint.org/docs/rules, and the IDs there are the same IDs you pass here, because, again, it is all the same core.

The `wrapper_depth` and `max_wrapper_depth` arguments let you control how deep the validator follows wrapper chains, which matters when you are validating a tag that is itself a wrapper several hops into a real serving scenario.

## A verifier for model and agent harnesses

There is a less obvious use for vastlint that has nothing to do with serving traffic, and it is the one I am most interested in: vastlint is a deterministic oracle for any system that generates VAST.

More and more teams are pointing language models at structured-output tasks, and "produce a valid VAST tag" is exactly that kind of task. A model that drafts a tag, repairs a broken one, or fills a template can produce something that looks right and parses fine and is still wrong in a way no exception will catch. To train, evaluate, or run such a model safely, you need a checker that is faster than the model, never hallucinates, and returns the same verdict every time. That is what a linter is, and that is precisely the gap a generative system cannot fill for itself.

vastlint fits that role cleanly because the output is structured rather than a blob of prose. You do not get back "looks good to me." You get a count of errors, the exact rules that failed, and a citation for each. That granularity is what lets you build a real signal instead of a binary one.

As a reward function in a training or rejection-sampling loop:

```python
import vastlint

def vast_reward(generated_xml: str) -> float:
    result = vastlint.validate(generated_xml)
    if result.valid:
        return 1.0
    # partial credit: penalize by severity, not just pass/fail
    s = result.summary
    return -1.0 * s.errors - 0.25 * s.warnings
```

Because the result carries per-rule detail, you can shape that reward however the task needs: hard-fail on any error, weight HTTPS violations heavier than a missing mezzanine, or reward getting from ten errors to one even when the tag is not yet clean. A binary valid/invalid throws away most of the signal the validator already computed for you.

As a verifier in an agent repair loop, the issue messages are the feedback. Each one has a human-readable message, the document path, and a spec citation, which is exactly the shape a model can read and act on:

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

That is generate, validate, feed the structured issues back, revise, repeat. The validator is the part of the loop that does not drift, and the `spec_ref` turns each failure into a teachable correction rather than a vague nudge.

The same properties make it a good eval harness. Run a model over a held-out set of dirty tags, validate every output, and you have a precise score: not just how many came out valid, but which rules each model gets wrong most often. And because validation is in-process and the Rust core clears a typical tag in well under a millisecond, you can run it across thousands of rollouts or eval samples without the validator becoming the bottleneck. A subprocess or a network call per rollout would dominate the loop; a function call does not.

If your harness is agent-shaped rather than a training loop, the same engine is also exposed as an MCP server, so an agent can call validation as a tool over the protocol instead of importing the package. Same rules, same verdicts, two ways in.

## How the package gets to PyPI

For the curious, the release path is worth a sentence because it is part of why you can trust the bytes. The Python package is built and published from a GitHub Actions workflow that vendors the platform-matched shared libraries straight from the corresponding `vastlint` release, runs the test suite, builds the sdist and wheel, runs `twine check` on the metadata, and publishes to PyPI using trusted publishing over OIDC. There is no long-lived API token sitting in a secret somewhere. The wheel you install is the artifact that passed those checks.

## Try it

```sh
pip install vastlint
```

```python
import vastlint
print(vastlint.version())
```

If you want to see the same engine in a browser first, the web validator is at vastlint.org/validate, and the rule catalog is at vastlint.org/docs/rules. The Python source lives at github.com/aleksUIX/vastlint-python.

If you have a Python ad tech backend and you have been putting off VAST validation because the options were all bad, the options are better now. It is one pip install and one function call.
