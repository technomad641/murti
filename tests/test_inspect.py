"""Offline tests for Vox Inspect's parsing/rendering (no REA, no network).

These exercise the pure functions against a tiny synthetic REA-style graph.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import murti.inspect as rx  # noqa: E402

# A miniature artifact graph shaped like REA's `inspect-artifact` JSON.
SAMPLE = {
    "subject": {"name": "demo.asar", "format": "asar",
                "digest": {"sha256": "a" * 64}},
    "provider": {"name": "REA safe artifact graph provider", "version": "1"},
    "normalized_result": {
        "contradictions": [
            {"statement": "Declared integrity for x/foo.node contradicts observed bytes."},
        ],
        "hypotheses": [{"statement": "May contain a recoverable graph."}],
        "next_probes": [
            {"operation": "analyze_javascript_application",
             "rationale": "Recover JS modules."},
        ],
        "coverage": {"status": "complete-within-substeps"},
        "substeps": [{"evidence": {"normalized_result": {"nodes": [
            {"logical_path": "package.json", "declared_size": 100},
            {"logical_path": ".webpack/main/index.js", "declared_size": 9_000_000},
            {"logical_path": ".webpack/main/native_modules/build/Release/node_sqlite3.node",
             "declared_size": 2_000_000},
            {"logical_path": ".webpack/main/opus_native.wasm", "declared_size": 300_000},
            {"logical_path": ".webpack/main/opusEncoder.worker.js", "declared_size": 500_000},
            {"logical_path": ".webpack/renderer/overlay/index.html", "declared_size": 1000},
            {"logical_path": ".webpack/renderer/overlay/preload.js", "declared_size": 500},
            {"logical_path": ".webpack/renderer/status/index.html", "declared_size": 1000},
            {"logical_path": ".webpack/main/native_modules/jabra-device-connector/win32/Jabra.NET.Sdk.dll",
             "declared_size": 100_000},
            {"logical_path": "dist/recorderWorklet.js", "declared_size": 1600},
        ]}}}],
    },
}


def test_collect_files_dedups_and_counts():
    files = rx.collect_files(SAMPLE)
    paths = {f["path"] for f in files}
    assert "package.json" in paths
    assert ".webpack/main/index.js" in paths
    # 10 distinct file paths in the sample
    assert len(files) == 10


def test_classify_buckets():
    b = rx.classify(rx.collect_files(SAMPLE))
    names = {f["path"].rsplit("/", 1)[-1] for f in b["native_addons"]}
    assert "node_sqlite3.node" in names
    assert any(f["path"].endswith(".wasm") for f in b["wasm"])
    assert "overlay" in b["renderer_windows"]
    assert "status" in b["renderer_windows"]
    assert b["has_package_json"] is True
    assert any("opusEncoder.worker.js" in f["path"] for f in b["workers"])


def test_feature_scan_finds_signals_and_no_asr():
    feats = rx.scan_features(rx.collect_files(SAMPLE))
    assert "Local database" in feats
    assert "Audio codec (Opus etc.)" in feats
    assert "Microphone / audio capture" in feats
    # No whisper/onnx/ggml in the sample -> ASR signal absent
    assert "On-device speech model (ASR)" not in feats


def test_clean_ex_strips_webpack_prefix():
    assert rx._clean_ex(".webpack/renderer/overlay/index.html") == "overlay/index.html"
    assert rx._clean_ex("a.node") == "a.node"


def test_render_contains_key_sections():
    md = rx.render(SAMPLE, "/tmp/demo.asar", "electron-asar",
                   {"name": "Demo", "version": "1.2.3",
                    "identifier": "com.demo.app"})
    for heading in ("# Architecture X-ray — Demo", "## Identity",
                    "## Native modules & addons", "## Processes & windows",
                    "## Feature signals", "## Integrity flags",
                    "## What REA suggests next"):
        assert heading in md, heading
    assert "1.2.3" in md
    assert "node_sqlite3.node" in md
    # Jabra connector file collapses into a summary row
    assert "jabra-device-connector/" in md
    # Integrity statement rendered (not a bare "?")
    assert "contradicts observed bytes" in md


def test_render_flags_missing_asr_model():
    md = rx.render(SAMPLE, "/tmp/demo.asar", "electron-asar", {"name": "Demo"})
    assert "No on-device speech model" in md


if __name__ == "__main__":
    # Dependency-free runner so `python3 test_teardown.py` works without pytest.
    import traceback

    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
