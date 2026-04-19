from typing import Any

import config

_VALID_VERDICTS = {"REAL", "FAKE", "UNCERTAIN"}


def synthesize(
    gemini: dict[str, Any],
    claude: dict[str, Any],
    gpt: dict[str, Any],
) -> dict[str, Any]:
    """
    Weighted vote synthesis.
    Each agent contributes: weight * (confidence / 100) to its verdict's score.
    Weights sum to 1.0, so final scores are in [0.0, 1.0].
    Final confidence = winning_score * 100.
    """
    scores: dict[str, float] = {"REAL": 0.0, "FAKE": 0.0, "UNCERTAIN": 0.0}
    agents = [
        (gemini, config.GEMINI_WEIGHT),
        (claude, config.CLAUDE_WEIGHT),
        (gpt, config.GPT_WEIGHT),
    ]

    for agent, weight in agents:
        verdict = agent.get("verdict", "UNCERTAIN").upper()
        if verdict not in _VALID_VERDICTS:
            verdict = "UNCERTAIN"
        confidence = max(0.0, min(1.0, agent.get("confidence", 50) / 100.0))
        scores[verdict] += weight * confidence

    # Guard: all-zero (all agents failed)
    if all(s == 0.0 for s in scores.values()):
        final_verdict = "UNCERTAIN"
        final_confidence = 0
    else:
        final_verdict = max(scores, key=scores.__getitem__)
        final_confidence = min(100, int(scores[final_verdict] * 100))

    # Consensus
    verdicts = [a.get("verdict", "UNCERTAIN").upper() for a, _ in agents]
    verdicts = [v if v in _VALID_VERDICTS else "UNCERTAIN" for v in verdicts]
    unique = set(verdicts)
    if len(unique) == 1:
        consensus = "UNANIMOUS"
    elif len(unique) == len(verdicts):
        consensus = "SPLIT"
    else:
        consensus = "MAJORITY"

    # Merge flags (deduplicated)
    all_flags: list[str] = list(
        {f for a, _ in agents for f in a.get("flags", [])}
    )

    # Combine reasoning from each agent
    reasoning_parts = []
    labels = ["Gemini", "Claude", "GPT"]
    for (agent, _), label in zip(agents, labels):
        r = agent.get("reasoning", "").strip()
        if r:
            reasoning_parts.append(f"{label}: {r}")
    combined_reasoning = " | ".join(reasoning_parts)

    return {
        "final_verdict": final_verdict,
        "confidence": final_confidence,
        "consensus": consensus,
        "reasoning": combined_reasoning,
        "flags": all_flags,
    }
