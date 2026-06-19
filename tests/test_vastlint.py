from pathlib import Path

import pytest

import vastlint

FIXTURES = Path(__file__).parent / "fixtures"
VALID = (FIXTURES / "valid.xml").read_text()
INVALID = (FIXTURES / "invalid.xml").read_text()


def test_version_matches_package():
    assert vastlint.version() == vastlint.__version__


def test_valid_tag_is_clean():
    result = vastlint.validate(VALID)
    assert result.valid is True
    assert result.summary.errors == 0
    assert result.version is not None


def test_invalid_tag_reports_errors():
    result = vastlint.validate(INVALID)
    assert result.valid is False
    assert result.summary.errors > 0
    assert any(issue.severity == "error" for issue in result.issues)
    first = result.issues[0]
    assert first.id
    assert first.message
    assert first.spec_ref


def test_accepts_bytes():
    result = vastlint.validate(INVALID.encode("utf-8"))
    assert result.valid is False


def test_to_dict_and_json_round_trip():
    result = vastlint.validate(INVALID)
    d = result.to_dict()
    assert set(d) == {"version", "issues", "summary"}
    assert set(d["summary"]) == {"errors", "warnings", "infos", "valid"}
    import json

    assert json.loads(result.to_json()) == d


def test_rule_overrides_can_silence_a_rule():
    base = vastlint.validate(INVALID)
    http_rule = "VAST-2.0-mediafile-https"
    assert any(i.id == http_rule for i in base.issues)

    overridden = vastlint.validate(INVALID, rule_overrides={http_rule: "off"})
    assert not any(i.id == http_rule for i in overridden.issues)


def test_empty_xml_rejected():
    with pytest.raises(ValueError):
        vastlint.validate("")


def test_bad_type_rejected():
    with pytest.raises(TypeError):
        vastlint.validate(123)  # type: ignore[arg-type]


def test_negative_wrapper_depth_rejected():
    with pytest.raises(ValueError):
        vastlint.validate(VALID, wrapper_depth=-1)
