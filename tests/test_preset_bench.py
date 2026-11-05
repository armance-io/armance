"""Preset bench — offline logic (loading, anonymisation, parsing, report)."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from armance.core.models.preset import PresetError, load_preset
from armance.service import preset_bench


def make_bench_pack(base: Path) -> Path:
    root = base / "demo"
    (root / "bench" / "cases" / "case-1").mkdir(parents=True)
    (root / "preset.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "bench" / "bench.yaml").write_text(
        "cases:\n"
        "  - id: case-1\n    workflow: wf-a\n    smoke: true\n    title: Premier cas\n"
        "  - id: case-2\n    workflow: wf-b\n",
        encoding="utf-8",
    )
    case = root / "bench" / "cases" / "case-1"
    (case / "input.md").write_text("Brief du cas.\n", encoding="utf-8")
    (case / "rubric.md").write_text("- pertinence\n- honnetete\n", encoding="utf-8")
    (case / "reference.md").write_text("Réponse idéale.\n", encoding="utf-8")
    (case / "attachments").mkdir()
    (case / "attachments" / "cr.md").write_text("CR.\n", encoding="utf-8")
    return root


class TestLoadBench:
    def test_load(self, tmp_path: Path) -> None:
        preset = load_preset(make_bench_pack(tmp_path))
        cases = preset_bench.load_bench(preset)
        assert [c.id for c in cases] == ["case-1", "case-2"]
        assert cases[0].smoke and not cases[1].smoke
        assert cases[0].workflow == "wf-a"
        assert [p.name for p in cases[0].attachments()] == ["cr.md"]
        assert cases[0].validate() == []
        assert len(cases[1].validate()) == 3  # case dir absent → 3 missing files

    def test_no_bench(self, tmp_path: Path) -> None:
        root = tmp_path / "p"
        root.mkdir()
        (root / "preset.yaml").write_text("name: p\n", encoding="utf-8")
        with pytest.raises(PresetError, match="no bench"):
            preset_bench.load_bench(load_preset(root))

    def test_case_missing_fields(self, tmp_path: Path) -> None:
        root = make_bench_pack(tmp_path)
        (root / "bench" / "bench.yaml").write_text(
            "cases:\n  - id: only-id\n", encoding="utf-8"
        )
        with pytest.raises(PresetError, match="id\\+workflow"):
            preset_bench.load_bench(load_preset(root))


class TestAnonymise:
    def test_both_sides_reachable_and_mapping_correct(self) -> None:
        sides = set()
        for seed in range(20):
            pair = preset_bench.anonymise_pair("ARM", "REF", random.Random(seed))
            sides.add(pair.armance_side)
            armance_text = pair.text_a if pair.armance_side == "A" else pair.text_b
            assert armance_text == "ARM"
        assert sides == {"A", "B"}


def _case(tmp_path: Path) -> preset_bench.BenchCase:
    preset = load_preset(make_bench_pack(tmp_path))
    return preset_bench.load_bench(preset)[0]


class TestJudgeParsing:
    def test_parse_scores_and_verdict(self, tmp_path: Path) -> None:
        case = _case(tmp_path)
        pair = preset_bench.AnonymisedPair("arm", "ref", armance_side="B")
        reply = (
            "| critère | A | B |\n|---|---|---|\n"
            "| pertinence | 6/10 | 8/10 |\n"
            "| honnetete | 7,5 | 9 |\n"
            "VERDICT: B\nJustification courte."
        )
        score = preset_bench.parse_judge_reply(case, pair, reply)
        assert score.scores["pertinence"] == (6.0, 8.0)
        assert score.scores["honnetete"] == (7.5, 9.0)
        assert score.verdict == "armance"  # B a gagné et Armance était B
        assert score.armance_mean == pytest.approx(8.5)
        assert score.reference_mean == pytest.approx(6.75)

    def test_verdict_deanonymised_to_reference(self, tmp_path: Path) -> None:
        case = _case(tmp_path)
        pair = preset_bench.AnonymisedPair("arm", "ref", armance_side="A")
        score = preset_bench.parse_judge_reply(case, pair, "VERDICT: B")
        assert score.verdict == "reference"

    def test_garbage_reply(self, tmp_path: Path) -> None:
        case = _case(tmp_path)
        pair = preset_bench.AnonymisedPair("arm", "ref", armance_side="A")
        score = preset_bench.parse_judge_reply(case, pair, "aucune table ici")
        assert score.scores == {}
        assert score.verdict == ""
        assert score.armance_mean == 0.0

    def test_judge_prompt_is_blind(self, tmp_path: Path) -> None:
        case = _case(tmp_path)
        pair = preset_bench.anonymise_pair("TEXTE_SYSTEME", "TEXTE_IDEAL")
        prompt = preset_bench.build_judge_prompt(case, pair, "grille")
        assert "armance" not in prompt.lower()
        assert "frontier" not in prompt.lower()
        import re

        assert not re.search(r"\bréférence\b", prompt.lower())
        assert "TEXTE_SYSTEME" in prompt and "TEXTE_IDEAL" in prompt


class TestReport:
    def _scores(self) -> list[preset_bench.CaseScore]:
        s = preset_bench.CaseScore(case_id="case-1", armance_side="A")
        s.scores = {"pertinence": (8.0, 7.0)}
        s.verdict = "armance"
        return [s]

    def test_render_with_delta(self, tmp_path: Path) -> None:
        report = preset_bench.render_report(
            "demo", "openrouter/x", self._scores(), previous={"case-1": 7.5}
        )
        assert "1 victoires Armance / 0 référence" in report
        assert "+0.5" in report
        assert "openrouter/x" in report

    def test_latest_means_roundtrip(self, tmp_path: Path) -> None:
        assert preset_bench.load_previous_means(tmp_path) is None
        preset_bench.save_latest_means(tmp_path, self._scores())
        assert preset_bench.load_previous_means(tmp_path) == {"case-1": 8.0}
