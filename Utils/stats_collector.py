"""
Statistics collector for the synthetic dialogue pipeline.

Tracks per-profile and global statistics including attempts, success rates,
judge scores, STS scores, and more.
"""

import logging
import json
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProfileStats:
    """Statistics for a single profile."""
    profile_id: str
    subject_id: int = 0
    hadm_id: int = 0
    row_id: int = 0
    profile_type: str = "UNKNOWN"
    light_case_filter_passed: bool = False
    light_case_filter_reason: str = ""

    # Attempt tracking
    attempts_total: int = 0
    success: bool = False
    success_attempt_index: Optional[int] = None

    # Judge scores per attempt
    judge_scores: List[float] = field(default_factory=list)
    judge_decisions: List[str] = field(default_factory=list)

    # Final metrics (for successful dialogues)
    final_judge_score: Optional[float] = None
    final_judge_decision: Optional[str] = None
    sts_score: Optional[float] = None

    # Processing metadata
    processing_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class StatsCollector:
    """Collects and aggregates statistics for the synthetic dialogue pipeline."""

    def __init__(self, output_dir: str = "outputs/stats"):
        """
        Initialize the StatsCollector.

        Args:
            output_dir: Directory to save statistics files.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.profile_stats: Dict[str, ProfileStats] = {}
        self.run_start_time = datetime.now()

        logger.info(f"StatsCollector initialized (output_dir={output_dir})")

    def create_profile_stats(self,
                            profile_id: str,
                            subject_id: int = 0,
                            hadm_id: int = 0,
                            row_id: int = 0,
                            profile_type: str = "UNKNOWN",
                            light_case_filter: Dict = None) -> ProfileStats:
        """
        Create a new ProfileStats entry.

        Args:
            profile_id: Unique profile identifier.
            subject_id: Subject ID from MIMIC-III.
            hadm_id: Hospital admission ID.
            row_id: Row ID from noteevents.
            profile_type: Type of profile (FULL, NO_DIAGNOSIS, etc.).
            light_case_filter: Light case filter result dict.

        Returns:
            ProfileStats object.
        """
        stats = ProfileStats(
            profile_id=profile_id,
            subject_id=subject_id,
            hadm_id=hadm_id,
            row_id=row_id,
            profile_type=profile_type
        )

        if light_case_filter:
            stats.light_case_filter_passed = light_case_filter.get('passed', False)
            stats.light_case_filter_reason = light_case_filter.get('reason', '')

        self.profile_stats[profile_id] = stats
        return stats

    def record_attempt(self,
                      profile_id: str,
                      attempt_index: int,
                      judge_score: float,
                      judge_decision: str) -> None:
        """
        Record a dialogue generation attempt.

        Args:
            profile_id: Profile identifier.
            attempt_index: Attempt number (1-based).
            judge_score: Judge's score (0.0-1.0).
            judge_decision: Judge's decision (REALISTIC/UNREALISTIC).
        """
        if profile_id not in self.profile_stats:
            logger.warning(f"Profile {profile_id} not found, creating entry")
            self.create_profile_stats(profile_id)

        stats = self.profile_stats[profile_id]
        stats.attempts_total = max(stats.attempts_total, attempt_index)
        stats.judge_scores.append(judge_score)
        stats.judge_decisions.append(judge_decision)

        if judge_decision == "REALISTIC" and not stats.success:
            stats.success = True
            stats.success_attempt_index = attempt_index
            stats.final_judge_score = judge_score
            stats.final_judge_decision = judge_decision

        logger.debug(f"Recorded attempt {attempt_index} for {profile_id}: {judge_decision} ({judge_score:.2f})")

    def record_sts_score(self, profile_id: str, sts_score: float) -> None:
        """
        Record STS score for a profile.

        Args:
            profile_id: Profile identifier.
            sts_score: STS similarity score (0.0-1.0).
        """
        if profile_id not in self.profile_stats:
            logger.warning(f"Profile {profile_id} not found for STS recording")
            return

        self.profile_stats[profile_id].sts_score = sts_score
        logger.debug(f"Recorded STS score for {profile_id}: {sts_score:.4f}")

    def record_processing_time(self, profile_id: str, processing_time: float) -> None:
        """
        Record processing time for a profile.

        Args:
            profile_id: Profile identifier.
            processing_time: Time in seconds.
        """
        if profile_id not in self.profile_stats:
            logger.warning(f"Profile {profile_id} not found for time recording")
            return

        self.profile_stats[profile_id].processing_time = processing_time

    def compute_global_stats(self) -> Dict:
        """
        Compute global statistics across all profiles.

        Returns:
            Dictionary with global statistics.
        """
        if not self.profile_stats:
            return {
                "error": "No profile statistics available"
            }

        total_profiles = len(self.profile_stats)
        successful_profiles = sum(1 for s in self.profile_stats.values() if s.success)
        failed_profiles = total_profiles - successful_profiles

        # Attempt statistics
        all_attempts = [s.attempts_total for s in self.profile_stats.values()]
        avg_attempts = sum(all_attempts) / len(all_attempts) if all_attempts else 0

        # Success by attempt
        success_by_attempt = {}
        for stats in self.profile_stats.values():
            if stats.success and stats.success_attempt_index:
                attempt = stats.success_attempt_index
                success_by_attempt[attempt] = success_by_attempt.get(attempt, 0) + 1

        # Judge score statistics
        successful_judge_scores = [
            s.final_judge_score
            for s in self.profile_stats.values()
            if s.success and s.final_judge_score is not None
        ]

        avg_judge_score = (
            sum(successful_judge_scores) / len(successful_judge_scores)
            if successful_judge_scores else None
        )
        min_judge_score = min(successful_judge_scores) if successful_judge_scores else None
        max_judge_score = max(successful_judge_scores) if successful_judge_scores else None

        # STS score statistics
        sts_scores = [
            s.sts_score
            for s in self.profile_stats.values()
            if s.sts_score is not None
        ]

        avg_sts_score = sum(sts_scores) / len(sts_scores) if sts_scores else None
        min_sts_score = min(sts_scores) if sts_scores else None
        max_sts_score = max(sts_scores) if sts_scores else None

        # Light case filter statistics
        light_case_passed = sum(
            1 for s in self.profile_stats.values()
            if s.light_case_filter_passed
        )

        # Profile type distribution
        profile_type_counts = {}
        for stats in self.profile_stats.values():
            ptype = stats.profile_type
            profile_type_counts[ptype] = profile_type_counts.get(ptype, 0) + 1

        # Timing statistics
        processing_times = [s.processing_time for s in self.profile_stats.values() if s.processing_time > 0]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        total_processing_time = sum(processing_times)

        # Run duration
        run_duration = (datetime.now() - self.run_start_time).total_seconds()

        global_stats = {
            "run_info": {
                "start_time": self.run_start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": run_duration
            },
            "profile_summary": {
                "total_profiles": total_profiles,
                "successful_profiles": successful_profiles,
                "failed_profiles": failed_profiles,
                "success_rate": successful_profiles / total_profiles if total_profiles > 0 else 0.0
            },
            "attempt_statistics": {
                "average_attempts": avg_attempts,
                "success_by_attempt": success_by_attempt
            },
            "judge_score_statistics": {
                "count": len(successful_judge_scores),
                "average": avg_judge_score,
                "min": min_judge_score,
                "max": max_judge_score
            },
            "sts_score_statistics": {
                "count": len(sts_scores),
                "average": avg_sts_score,
                "min": min_sts_score,
                "max": max_sts_score
            },
            "light_case_filter": {
                "total_evaluated": total_profiles,
                "passed": light_case_passed,
                "pass_rate": light_case_passed / total_profiles if total_profiles > 0 else 0.0
            },
            "profile_type_distribution": profile_type_counts,
            "processing_time": {
                "average_per_profile": avg_processing_time,
                "total_processing_time": total_processing_time
            }
        }

        return global_stats

    def save_per_profile_stats(self, filename: str = "per_profile_stats.json") -> None:
        """
        Save per-profile statistics to JSON file.

        Args:
            filename: Output filename.
        """
        output_path = self.output_dir / filename

        stats_list = [stats.to_dict() for stats in self.profile_stats.values()]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats_list, f, indent=2)

        logger.info(f"Saved per-profile stats to {output_path} ({len(stats_list)} profiles)")

    def save_global_stats(self, filename: str = "global_stats.json") -> None:
        """
        Save global statistics to JSON file.

        Args:
            filename: Output filename.
        """
        output_path = self.output_dir / filename

        global_stats = self.compute_global_stats()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(global_stats, f, indent=2)

        logger.info(f"Saved global stats to {output_path}")

    def save_all_stats(self) -> None:
        """Save both per-profile and global statistics."""
        self.save_per_profile_stats()
        self.save_global_stats()

    def print_summary(self) -> None:
        """Print a summary of global statistics to the console."""
        global_stats = self.compute_global_stats()

        print("\n" + "=" * 60)
        print("SYNTHETIC DIALOGUE PIPELINE - STATISTICS SUMMARY")
        print("=" * 60)

        if "error" in global_stats:
            print(f"Error: {global_stats['error']}")
            return

        summary = global_stats["profile_summary"]
        print(f"\nProfiles Processed: {summary['total_profiles']}")
        print(f"Successful: {summary['successful_profiles']}")
        print(f"Failed: {summary['failed_profiles']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")

        attempt_stats = global_stats["attempt_statistics"]
        print(f"\nAverage Attempts per Profile: {attempt_stats['average_attempts']:.2f}")

        if attempt_stats['success_by_attempt']:
            print("Success by Attempt:")
            for attempt, count in sorted(attempt_stats['success_by_attempt'].items()):
                print(f"  Attempt {attempt}: {count} profiles")

        judge_stats = global_stats["judge_score_statistics"]
        if judge_stats['average'] is not None:
            print(f"\nJudge Scores (Successful Dialogues):")
            print(f"  Average: {judge_stats['average']:.3f}")
            print(f"  Range: {judge_stats['min']:.3f} - {judge_stats['max']:.3f}")

        sts_stats = global_stats["sts_score_statistics"]
        if sts_stats['average'] is not None:
            print(f"\nSTS Scores:")
            print(f"  Average: {sts_stats['average']:.4f}")
            print(f"  Range: {sts_stats['min']:.4f} - {sts_stats['max']:.4f}")

        timing = global_stats["processing_time"]
        print(f"\nProcessing Time:")
        print(f"  Average per Profile: {timing['average_per_profile']:.1f}s")
        print(f"  Total: {timing['total_processing_time']:.1f}s")

        print("=" * 60 + "\n")
