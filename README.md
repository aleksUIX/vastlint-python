# vastlint (Python)

High-performance, in-process VAST XML validation for Python backends.

**Rule reference:** [vastlint.org/docs/rules](https://vastlint.org/docs/rules/) · **Web validator:** [vastlint.org/validate](https://vastlint.org/validate)

This package wraps the stable `vastlint-ffi` C API, backed by the same Rust core used by the CLI, Go binding, Ruby gem, Erlang NIF, MCP server, and web validator. The intended use case is a DSP, SSP, ad server, or trafficking backend that needs to validate VAST XML and return structured linting results to a frontend.

## Why this shape

- No subprocess management in your Python app
- No network hop to an external validation service
- Stable JSON-compatible result shape for backend-to-frontend responses
- Same rule coverage and behavior as the rest of the vastlint ecosystem

## Install

The package bundles a platform-matched `libvastlint` shared library inside the wheel, so no compiler or Rust toolchain is needed at install time.

```sh
pip install vastlint
```

You can also point the package at an explicit shared library with `VASTLINT_LIB_PATH`:

```sh
export VASTLINT_LIB_PATH=/absolute/path/to/libvastlint.dylib
```

For development in this monorepo, it automatically falls back to the sibling `vastlint/target/debug` and `vastlint/target/release` outputs.

## Usage

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

### FastAPI / Flask example

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

The response shape is stable and frontend-friendly:

```json
{
  "version": "4.2",
  "issues": [
    {
      "id": "VAST-2.0-inline-impression",
      "severity": "error",
      "message": "<InLine> must contain at least one <Impression>",
      "path": "/VAST/Ad[0]/InLine",
      "spec_ref": "IAB VAST 2.0 §2.2.1",
      "line": 4,
      "col": 3
    }
  ],
  "summary": { "errors": 1, "warnings": 0, "infos": 0, "valid": false }
}
```

## API

```python
vastlint.validate(xml, *, wrapper_depth=0, max_wrapper_depth=5, rule_overrides=None) -> Result
vastlint.version() -> str
```

`xml` accepts `str` or `bytes`. `rule_overrides` maps rule IDs to severity levels:

```python
result = vastlint.validate(
    vast_xml,
    rule_overrides={
        "VAST-2.0-mediafile-https": "error",
        "VAST-4.1-mezzanine-recommended": "off",
    },
)
```

`Result` exposes `.version`, `.issues` (list of `Issue`), `.summary` (`Summary`), `.valid`, `.to_dict()`, and `.to_json()`. All result types are frozen dataclasses.

## Native library layout

Vendored release libraries live at:

- `src/vastlint/native/darwin_arm64/libvastlint.dylib`
- `src/vastlint/native/darwin_amd64/libvastlint.dylib`
- `src/vastlint/native/linux_arm64/libvastlint.so`
- `src/vastlint/native/linux_amd64/libvastlint.so`

They come from the `vastlint-ffi-*` tarballs attached to each `vastlint` GitHub Release. Refresh them with:

```sh
./scripts/fetch-libs.sh v0.4.14
```

## License

Apache 2.0.
