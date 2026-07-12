from herpeakgem.learning.mastery import BKTParameters, compute_bkt_mastery


def test_bkt_correct_answer_raises_mastery_and_includes_learning_transition():
    params = BKTParameters(prior=0.2, learn=0.15, guess=0.2, slip=0.1)
    assert compute_bkt_mastery([True], params) > params.prior


def test_bkt_wrong_answer_reduces_mastery_but_learning_keeps_state_bounded():
    params = BKTParameters(prior=0.6, learn=0.1, guess=0.2, slip=0.1)
    value = compute_bkt_mastery([False], params)
    assert 0.0 < value < params.prior


def test_bkt_rejects_invalid_probability_parameters():
    try:
        BKTParameters(prior=1.1)
    except ValueError as exc:
        assert "0..1" in str(exc)
    else:
        raise AssertionError("invalid probability must fail")
