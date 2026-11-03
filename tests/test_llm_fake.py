from forecaster.forecast_prompt import parse_probability
from forecaster.llm.fake import FakeLLM


def test_fake_llm_always_parseable():
    llm = FakeLLM()
    for _ in range(20):
        completion = llm.complete(
            system="sys", user="Will it rain?", temperature=0.7, max_tokens=50
        )
        prob = parse_probability(completion)
        assert prob is not None
        assert 0.0 <= prob <= 1.0


def test_fake_llm_varies_across_calls():
    llm = FakeLLM()
    probs = {parse_probability(llm.complete("sys", "same question", 0.7, 50)) for _ in range(10)}
    assert len(probs) > 1


def test_fake_llm_deterministic_given_fresh_instance():
    probs_a = [parse_probability(FakeLLM().complete("sys", "Q", 0.7, 50)) for _ in range(1)]
    probs_b = [parse_probability(FakeLLM().complete("sys", "Q", 0.7, 50)) for _ in range(1)]
    assert probs_a == probs_b
