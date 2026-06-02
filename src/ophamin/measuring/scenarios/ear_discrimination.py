"""Ear Discrimination — does a learned-from-scratch ear give a discriminating audio address
on REAL sounds, where the live 5-stat encoder does not?

The signed validation of the EAR campaign (journal 054). The live audio path is the hand-crafted
5-stat `AudioGeoidEncoder` (→ 5-D), whose address is no better than a random projection. A
learned ear (small CNN on the log-mel spectrogram, from scratch, NO pretrained weights) recovers
the discrimination. This attests it on REAL data (ESC-50: 50 environmental-sound classes × 2000
WAV @ 44.1 kHz), held-out, leakage-clean:

  primary    : learned-ear held-out prec@5 >= 0.33  (clearly beats raw log-mel ~0.227)
  contrast   : the 5-stat ear and raw log-mel prec@5 on the same held-out fold

Loads the cached log-mel spectrograms + the learned-ear weights (trained on folds 1-4); evaluates
on fold 5 (ESC-50 folds are source-disjoint — no clip leakage). Real audio, no synthetic data.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import statsmodels as _sm  # noqa: F401

from ophamin import __version__
from ophamin.comparing.provenance.lineage import _ophamin_project_root, capture_git_commit
from ophamin.measuring.proof import (
    Claim, DatasetRef, EmpiricalProofRecord, PillarEvidence, PreRegistration,
    Reproduction, Threshold, Verdict, content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_KIMERA = Path("/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)")
_CACHE = _KIMERA / "experiments/observatory/runs/ear/esc50_cache.npz"
_WEIGHTS = _KIMERA / "experiments/observatory/runs/ear/ear_m1.pt"
_ESC50 = Path("/Volumes/Kaido/Foreign_Corpus/sensory_audio/ESC-50-master")
N_MELS, N_FRAMES, HELD_OUT_FOLD = 64, 128, 5


def _metrics(addr, labels, k=5):
    A = addr.astype(np.float64)
    A = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
    S = A @ A.T
    n = len(labels)
    same = labels[:, None] == labels[None, :]
    off = ~np.eye(n, dtype=bool)
    within = float(S[same & off].mean())
    cross = float(S[~same].mean())
    np.fill_diagonal(S, -np.inf)
    nn = np.argsort(-S, axis=1)[:, :k]
    nn_lab = labels[nn]
    return {"margin": within - cross, "prec@5": float((nn_lab == labels[:, None]).mean())}


class EarDiscriminationScenario(Scenario):
    """A learned-from-scratch ear gives a discriminating audio address on real sounds; the
    live 5-stat encoder does not."""

    name = "ear-discrimination"
    tier = Tier.SCIENTIFIC
    family = "audio_ear"
    goal = ("Does a learned-from-scratch ear give a discriminating audio address on real ESC-50 "
            "sounds, where the live 5-stat AudioGeoidEncoder does not?")
    explanation = (
        "The live audio path is a hand-crafted 5-stat encoder whose address is no better than a "
        "random projection. A learned ear (small CNN on the log-mel spectrogram, from scratch, no "
        "pretrained weights) recovers the discrimination. Measured on real ESC-50, held-out, "
        "leakage-clean: learned-ear prec@5 vs the 5-stat ear and raw log-mel."
    )
    method = "ear_holdout_prec_at_5"
    falsification_consequence = (
        "If the learned-ear held-out prec@5 <= 0.33 (does not clearly beat raw log-mel ~0.227), a "
        "learned ear does not recover audio discrimination on real data — the door is not faithful."
    )
    runner_path = "examples/run_ear_discrimination.py"

    def __init__(self, *, accuracy_floor: float = 0.33, target: str = "entity") -> None:
        self.accuracy_floor = float(accuracy_floor)
        self.target = target
        self.corpus_name = "esc50-real-audio"
        self.n_cycles = 0

    def score(self, cycle_results: list[CycleResult], records: list[CorpusRecord]) -> ScenarioScore:
        raise NotImplementedError("EarDiscriminationScenario uses a custom run() loop.")

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"A learned-from-scratch ear gives a discriminating audio address on real ESC-50 "
                f"sounds: held-out (source-disjoint fold {HELD_OUT_FOLD}) prec@5 >= "
                f"{self.accuracy_floor:.2f}, clearly beating raw log-mel (~0.227) and the live "
                f"5-stat encoder (~0.13 ≈ a random projection)."
            ),
            operationalization=(
                "ESC-50 (50 classes × 2000 WAV); log-mel 64×128; a small from-scratch CNN ear "
                "(no pretrained weights) trained on folds 1-4; address = penultimate embedding; "
                "held-out fold-5 prec@5 (within−cross cosine NN), vs the 5-stat AudioGeoidEncoder "
                "and raw log-mel mean-pooled on the same fold."
            ),
            threshold=Threshold(metric="ear_holdout_prec_at_5", comparator=">=",
                                value=self.accuracy_floor, units="precision@5"),
            h0="H0: learned-ear prec@5 < 0.33 — a learned ear does not recover audio discrimination",
            h1=f"H1: learned-ear prec@5 >= {self.accuracy_floor:.2f} — a faithful learned ear",
        )

    def analysis_plan(self) -> str:
        return ("Load cached ESC-50 log-mel + learned-ear weights (folds 1-4); embed held-out "
                "fold 5; prec@5 for learned vs 5-stat vs raw log-mel; report the contrast.")

    def run(self, substrate: SubstrateUnderTest, *, data_root=None,
            sign_key: bytes = DEFAULT_SIGN_KEY) -> EmpiricalProofRecord:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        if not (_CACHE.exists() and _WEIGHTS.exists()):
            raise RuntimeError("ear-discrimination: need esc50_cache.npz + ear_m1.pt "
                               "(run ear_baseline_probe + ear_m1_learned_probe first)")
        d = np.load(_CACHE)
        specs, labels, folds, pos5 = d["specs"], d["labels"], d["folds"], d["pos5"]
        # B614 (Ophamin lint policy): weights_only=True enforces torch's
        # restricted unpickler so a malicious .pt cannot execute arbitrary
        # code on load. The cached file contains only model state_dict +
        # mu/sd tensors (built by ear_m1_learned_probe), so the restricted
        # loader accepts it.
        ck = torch.load(_WEIGHTS, map_location="cpu", weights_only=True)
        mu, sd = ck["mu"], ck["sd"]

        class Ear(nn.Module):  # matches ear_m1_learned_probe (3 conv blocks)
            def __init__(self, emb=128, n_cls=50):
                super().__init__()
                self.c1 = nn.Conv2d(1, 32, 3, padding=1)
                self.b1 = nn.BatchNorm2d(32)
                self.c2 = nn.Conv2d(32, 64, 3, padding=1)
                self.b2 = nn.BatchNorm2d(64)
                self.c3 = nn.Conv2d(64, 128, 3, padding=1)
                self.b3 = nn.BatchNorm2d(128)
                self.fc = nn.Linear(128, emb)
                self.head = nn.Linear(emb, n_cls)

            def embed(self, x):
                x = F.max_pool2d(F.relu(self.b1(self.c1(x))), 2)
                x = F.max_pool2d(F.relu(self.b2(self.c2(x))), 2)
                x = F.relu(self.b3(self.c3(x)))
                return self.fc(F.adaptive_avg_pool2d(x, 1).flatten(1))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ear = Ear()
            ear.load_state_dict(ck["state"])
            ear.eval()
            te = folds == HELD_OUT_FOLD
            specs_n = (specs[te].astype(np.float32) - mu) / sd
            emb = ear.embed(torch.from_numpy(specs_n).unsqueeze(1)).detach().numpy()

        lab_te = labels[te]
        learned = _metrics(emb, lab_te)
        five = _metrics(pos5[te], lab_te)
        raw = _metrics(specs[te].reshape(int(te.sum()), N_MELS, N_FRAMES).mean(axis=2), lab_te)
        observed = float(learned["prec@5"])
        chance = 1.0 / len(set(labels.tolist()))

        claim = self.build_claim()
        dataset = DatasetRef(
            name="esc50-real-audio",
            content_hash=content_hash({"n_heldout": int(te.sum()), "fold": HELD_OUT_FOLD,
                                       "weights": str(_WEIGHTS)}),
            n_records=int(te.sum()), source=str(_ESC50),
            kind="real environmental-sound clips (held-out source-disjoint fold)",
        )
        prereg = PreRegistration(
            config_hash=content_hash({"scenario": self.name, "floor": self.accuracy_floor,
                                      "fold": HELD_OUT_FOLD}),
            data_hash=dataset.content_hash, analysis_plan=self.analysis_plan(),
        )
        verdict = Verdict.decide(observed=observed, threshold=claim.threshold, reasoning=(
            f"learned-ear held-out prec@5 {observed:.4f} (margin {learned['margin']:.3f}) over "
            f"{int(te.sum())} real clips, 50 classes (chance {chance:.3f}); 5-stat "
            f"{five['prec@5']:.4f} (margin {five['margin']:.3f} ≈ random); raw log-mel "
            f"{raw['prec@5']:.4f}"))
        evidence = [PillarEvidence(
            pillar="audio_address_discrimination", statistic_name="ear_holdout_prec_at_5",
            statistic_value=observed, library="numpy", library_version=np.__version__,
            effect_size=observed - raw["prec@5"], ci_low=0.0, ci_high=0.0, p_value=None,
            cross_check="passed" if observed >= self.accuracy_floor > five["prec@5"] else "failed",
            detail={"n_heldout": int(te.sum()), "n_classes": len(set(labels.tolist())),
                    "chance": chance, "learned_prec5": observed, "learned_margin": learned["margin"],
                    "fivestat_prec5": five["prec@5"], "fivestat_margin": five["margin"],
                    "raw_logmel_prec5": raw["prec@5"], "held_out_fold": HELD_OUT_FOLD,
                    "note": "5-fold CV mean prec@5 (probe) 0.469±0.009; this signs the leakage-clean single fold"},
        )]
        record = EmpiricalProofRecord(
            claim=claim, preregistration=prereg, datasets=[dataset],
            substrate_name=substrate.name, substrate_git_commit=substrate.git_commit(),
            evidence=evidence, verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=self._build_provenance(substrate, dataset).to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
