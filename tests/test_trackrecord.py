from dataclasses import dataclass
from datetime import UTC, datetime

from forecaster import trackrecord


@dataclass
class _FakeForecastRow:
    question_id: str
    created_at: datetime
    model: str
    prompt_version: str
    prompt_sha256: str
    raw_prob: float
    calibrated_prob: float
    calibrator_version: str
    prev_hash: str = ""
    hash: str = ""


def _build_chain(n=3):
    rows = []
    prev_hash = trackrecord.GENESIS_HASH
    for i in range(n):
        row = _FakeForecastRow(
            question_id=f"demo:{i}",
            created_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
            model="fake-v1",
            prompt_version="forecast_v1",
            prompt_sha256="abc123",
            raw_prob=0.5 + i * 0.01,
            calibrated_prob=0.5 + i * 0.01,
            calibrator_version="identity",
        )
        fields = trackrecord.hashable_fields(row)
        row.prev_hash = prev_hash
        row.hash = trackrecord.compute_hash(prev_hash, fields)
        rows.append(row)
        prev_hash = row.hash
    return rows


def test_compute_hash_is_deterministic():
    row = _build_chain(1)[0]
    fields = trackrecord.hashable_fields(row)
    h1 = trackrecord.compute_hash(trackrecord.GENESIS_HASH, fields)
    h2 = trackrecord.compute_hash(trackrecord.GENESIS_HASH, fields)
    assert h1 == h2
    assert h1 == row.hash


def test_verify_chain_passes_on_untampered_chain():
    rows = _build_chain(5)
    assert trackrecord.verify_chain(rows) is None


def test_verify_chain_detects_tampering():
    rows = _build_chain(5)
    rows[2].raw_prob = 0.999  # edit history without recomputing the chain
    result = trackrecord.verify_chain(rows)
    assert result is not None
    assert result.index == 2


def test_build_site_writes_hash_verified_manifest(tmp_path):
    @dataclass
    class _Q:
        id: str
        title: str
        url: str
        status: str
        resolution: float | None

    questions = [
        _Q(
            id="demo:0",
            title="Will it happen?",
            url="https://x.invalid",
            status="resolved",
            resolution=1.0,
        )
    ]
    rows = _build_chain(1)
    rows[0].question_id = "demo:0"

    out_dir = tmp_path / "public"
    trackrecord.build_site(str(out_dir), questions, {"demo:0": rows})

    import json

    manifest = json.loads((out_dir / "manifest.json").read_text())
    for name, expected_hash in manifest["files"].items():
        assert trackrecord.sha256_file(out_dir / name) == expected_hash
