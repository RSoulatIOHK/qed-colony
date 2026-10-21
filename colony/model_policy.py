"""Deterministic, bounded model routing; proof acceptance is independent of it."""

DEFAULT_TIERS = (
    {"model": "gpt-6-luna", "reasoning_effort": "medium"},
    {"model": "gpt-6-sol", "reasoning_effort": "high"},
    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
)


def choose_model(policy, role, stage, revision=0, trust_critical=False):
    """Start small; explicit failed-attempt revisions and proof reviews escalate.

    The controller supplies revision and trust flags, never the worker. Model
    selection does not waive review, CI, or kernel checking. This initial policy
    learns from failures within a task, rather than claiming a trained router.
    """
    tiers = policy.get("model_tiers", list(DEFAULT_TIERS))
    if not isinstance(tiers, list) or not 1 <= len(tiers) <= 3:
        raise ValueError("model_tiers must contain between one and three models")
    for tier in tiers:
        if (not isinstance(tier, dict) or not isinstance(tier.get("model"), str)
                or not tier["model"].strip() or tier.get("reasoning_effort") not in {"low", "medium", "high"}):
            raise ValueError("Each model tier needs a model and low/medium/high reasoning_effort")
    if type(revision) is not int or revision < 0:
        raise ValueError("revision must be a nonnegative integer")
    starting_tier = min(1, len(tiers) - 1) if trust_critical else 0
    tier_index = min(starting_tier + revision, len(tiers) - 1)
    reason = ("Escalated after %d failed attempt(s) or requested revision(s)" % revision if revision else
              "Stronger independent review for proof or trust-sensitive changes" if trust_critical else
              "Small model first for %s %s" % (role, stage))
    return dict(tiers[tier_index], reason=reason, tier=tier_index)
