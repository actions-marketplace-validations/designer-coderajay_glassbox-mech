"""Executable checks for docs/v7/SECURITY_PRIVACY.md (V7 Hard Gate 10).

Each test pins one documented control **or one documented limitation**, so the document
cannot silently drift from the code. Limitations are tested as limitations: if one is
ever fixed, its test fails and the document must be updated.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import socket

import pytest

from glassbox.v7 import otlp
from glassbox.v7.evidence import EvidenceError, PackageSpec, build_package
from glassbox.v7.trace import Recorder, canonical_json, read_trace, redact

SECRET = "Patient Jane Roe, born 1984-03-02, phone +49 151 2345678, jane@example.org"


def _record(tmp_path, policy="hash_only", content=SECRET):
    with Recorder(out_dir=tmp_path, run_id="r", content_policy=policy) as rec:
        with rec.span("chat", "m", content={"gen_ai.input.messages": content}):
            pass
    return tmp_path / "r.trace.jsonl"


def test_c1_hash_only_default_writes_no_raw_content(tmp_path):
    with Recorder(out_dir=tmp_path, run_id="r") as rec:
        with rec.span("chat", "m", content={"gen_ai.input.messages": SECRET}):
            pass
    text = (tmp_path / "r.trace.jsonl").read_text()
    assert "Jane" not in text and "jane@example.org" not in text and "151" not in text


def test_c2_content_cannot_bypass_policy(tmp_path):
    with Recorder(out_dir=tmp_path, run_id="r") as rec:
        with pytest.raises(ValueError):
            with rec.span("chat", "m", attributes={"gen_ai.input.messages": SECRET}):
                pass


def test_l1_hash_only_is_not_anonymisation(tmp_path):
    """Limitation: unsalted SHA-256 of guessable content can be confirmed by anyone."""
    spans, _ = read_trace(_record(tmp_path, content="yes"))
    stored = spans[1]["attributes"]["glassbox.content.gen_ai.input.messages.sha256"]
    guess = hashlib.sha256(canonical_json("yes").encode("utf-8")).hexdigest()
    assert stored == guess


def test_l2_redaction_is_best_effort(tmp_path):
    """Limitation: only e-mail addresses and API-key patterns are redacted."""
    out = redact(SECRET)
    assert "[REDACTED:email]" in out
    assert "Jane Roe" in out and "+49 151 2345678" in out and "1984-03-02" in out
    assert "sk-" not in redact("key sk-ABCDEFGHIJKLMNOPQRST1234")


def test_c3_full_policy_requires_explicit_opt_in(tmp_path):
    text = _record(tmp_path, policy="full").read_text()
    root = json.loads(text.splitlines()[0])
    assert root["attributes"]["glassbox.content.policy"] == "full"
    assert "Jane Roe" in text


def test_c4_environment_has_no_user_or_host_name(tmp_path):
    text = _record(tmp_path).read_text()
    user = getpass.getuser()
    host = socket.gethostname().split(".")[0]
    root = json.loads(text.splitlines()[0])["attributes"]
    env = {k for k in root if k.startswith("glassbox.env.")}
    assert env == {"glassbox.env.python", "glassbox.env.platform"}
    if len(user) > 3:
        assert user not in text
    if len(host) > 3:
        assert host not in text


def test_c5_integrity_detects_tampering_but_not_truth(tmp_path):
    path = _record(tmp_path)
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace('"chat"', '"chaT"')
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        read_trace(path)


def test_c6_otlp_import_hashes_content_and_drops_vectors():
    data = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "0af7651916cd43dd8448eb211c80319c",
                                "spanId": "b7ad6b7169203331",
                                "name": "q",
                                "attributes": [
                                    {
                                        "key": "input.value",
                                        "value": {"stringValue": SECRET},
                                    },
                                    {
                                        "key": "embedding.embeddings.0.embedding.vector",
                                        "value": {"arrayValue": {"values": []}},
                                    },
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }
    res = otlp.import_otlp(data)
    assert "Jane" not in json.dumps(res.spans) and res.vectors_dropped == 1
    with pytest.raises(ValueError):
        otlp.import_otlp(data, content_policy="full")


def test_c7_evidence_never_overwrites_and_reproduced_needs_reproducer(tmp_path):
    art = tmp_path / "a.txt"
    art.write_text("x")
    ok = PackageSpec("c", "PRELIMINARY", "s", {"m": [art]}, {})
    build_package(tmp_path / "out", "p", ok)
    with pytest.raises(FileExistsError):
        build_package(tmp_path / "out", "p", ok)
    bad = PackageSpec("c", "REPRODUCED", "s", {"m": [art]}, {})
    with pytest.raises(EvidenceError):
        build_package(tmp_path / "out2", "p", bad)


def test_c8_traces_are_never_overwritten(tmp_path):
    _record(tmp_path)
    with pytest.raises(FileExistsError):
        _record(tmp_path)
