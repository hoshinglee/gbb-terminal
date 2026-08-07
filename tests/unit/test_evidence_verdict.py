from gbb_terminal.backtesting.metrics import EvidenceContext, evidence_verdict


STRONG_METRICS = {
    "trades": 30,
    "excessReturn": 12.0,
    "sharpeRatio": 1.4,
    "calmarRatio": 1.1,
}


def test_strong_single_window_result_is_not_called_robust():
    verdict = evidence_verdict(STRONG_METRICS)

    assert verdict["label"] == "Promising But Unstable"
    assert "independently confirmed" in verdict["reason"]


def test_robust_verdict_requires_holdout_stability_and_selection_adjustment():
    context = EvidenceContext(
        out_of_sample=True,
        stable_parameters=True,
        deflated_sharpe_probability=0.85,
        walk_forward_folds=3,
    )

    assert evidence_verdict(STRONG_METRICS, context)["label"] == "Robust Candidate"
    assert evidence_verdict(STRONG_METRICS, EvidenceContext(out_of_sample=True))["label"] != "Robust Candidate"
