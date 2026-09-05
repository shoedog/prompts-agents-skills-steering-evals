"""Statistical reducers for paired evaluation results."""

from harness.stats.bootstrap import mean_outcome, paired_delta_ci, percentile
from harness.stats.paired import flips

__all__ = ["flips", "mean_outcome", "paired_delta_ci", "percentile"]
