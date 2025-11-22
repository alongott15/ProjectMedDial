"""Stats Collector Agent - Collects and computes experiment statistics"""
import json
import logging
from pathlib import Path
from typing import Dict, List
import statistics

logger = logging.getLogger(__name__)


class StatsCollectorAgent:
    """Collects and computes statistics for the experiment"""

    def __init__(self, output_dir: str = "outputs/stats"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.per_profile_stats = []
        self.global_stats = {
            "ehr_cases_retrieved": 0,
            "light_cases_passed": 0,
            "gtmfs_created": 0,
            "gtmfs_failed": 0,
            "profiles_generated": {},
            "dialogues_generated": 0,
            "dialogue_success_rate": {},
            "sts_scores": []
        }

    def add_profile_stats(self, profile_stat: Dict):
        """Add statistics for a single profile"""
        self.per_profile_stats.append(profile_stat)

    def update_global_stats(self, key: str, value):
        """Update global statistics"""
        self.global_stats[key] = value

    def compute_dialogue_stats(self):
        """Compute dialogue generation statistics"""
        if not self.per_profile_stats:
            return

        attempts_1 = sum(1 for p in self.per_profile_stats if p.get("success") and p.get("success_attempt_index") == 1)
        attempts_2 = sum(1 for p in self.per_profile_stats if p.get("success") and p.get("success_attempt_index") == 2)
        attempts_3 = sum(1 for p in self.per_profile_stats if p.get("success") and p.get("success_attempt_index") == 3)
        failed = sum(1 for p in self.per_profile_stats if not p.get("success"))

        total = len(self.per_profile_stats)

        self.global_stats["dialogue_success_rate"] = {
            "success_attempt_1": attempts_1,
            "success_attempt_2": attempts_2,
            "success_attempt_3": attempts_3,
            "failed_after_3_attempts": failed,
            "total_profiles": total,
            "success_rate_pct": (total - failed) / total * 100 if total > 0 else 0
        }

    def compute_sts_stats(self):
        """Compute STS statistics"""
        if not self.per_profile_stats:
            return

        sts_scores = [p.get("sts_score", 0) for p in self.per_profile_stats if p.get("sts_score") is not None]

        if sts_scores:
            self.global_stats["sts_scores"] = {
                "mean": statistics.mean(sts_scores),
                "std": statistics.stdev(sts_scores) if len(sts_scores) > 1 else 0,
                "min": min(sts_scores),
                "max": max(sts_scores),
                "count": len(sts_scores)
            }

            # Per profile type
            profile_types = {}
            for profile in self.per_profile_stats:
                profile_type = profile.get("profile_type", "UNKNOWN")
                if profile_type not in profile_types:
                    profile_types[profile_type] = []
                if profile.get("sts_score") is not None:
                    profile_types[profile_type].append(profile.get("sts_score"))

            self.global_stats["sts_by_profile_type"] = {
                ptype: {
                    "mean": statistics.mean(scores),
                    "count": len(scores)
                }
                for ptype, scores in profile_types.items() if scores
            }

    def save_stats(self):
        """Save all statistics to JSON"""
        # Compute final statistics
        self.compute_dialogue_stats()
        self.compute_sts_stats()

        # Save per-profile stats
        per_profile_path = self.output_dir / "per_profile_stats.json"
        with open(per_profile_path, 'w', encoding='utf-8') as f:
            json.dump(self.per_profile_stats, f, indent=2)
        logger.info(f"Saved per-profile stats to {per_profile_path}")

        # Save global stats
        global_path = self.output_dir / "global_stats.json"
        with open(global_path, 'w', encoding='utf-8') as f:
            json.dump(self.global_stats, f, indent=2)
        logger.info(f"Saved global stats to {global_path}")

        return str(per_profile_path), str(global_path)

    def print_summary(self):
        """Print a summary of statistics"""
        print("\n" + "=" * 60)
        print("EXPERIMENT STATISTICS SUMMARY")
        print("=" * 60)

        print(f"\nEHR Retrieval:")
        print(f"  Total retrieved: {self.global_stats.get('ehr_cases_retrieved', 0)}")
        print(f"  Light cases passed: {self.global_stats.get('light_cases_passed', 0)}")

        print(f"\nGTMF Creation:")
        print(f"  Created: {self.global_stats.get('gtmfs_created', 0)}")
        print(f"  Failed: {self.global_stats.get('gtmfs_failed', 0)}")

        print(f"\nProfile Generation:")
        for ptype, count in self.global_stats.get('profiles_generated', {}).items():
            print(f"  {ptype}: {count}")

        dialogue_stats = self.global_stats.get('dialogue_success_rate', {})
        if dialogue_stats:
            print(f"\nDialogue Generation:")
            print(f"  Success on attempt 1: {dialogue_stats.get('success_attempt_1', 0)}")
            print(f"  Success on attempt 2: {dialogue_stats.get('success_attempt_2', 0)}")
            print(f"  Success on attempt 3: {dialogue_stats.get('success_attempt_3', 0)}")
            print(f"  Failed after 3 attempts: {dialogue_stats.get('failed_after_3_attempts', 0)}")
            print(f"  Overall success rate: {dialogue_stats.get('success_rate_pct', 0):.1f}%")

        sts_stats = self.global_stats.get('sts_scores', {})
        if sts_stats:
            print(f"\nSTS Evaluation:")
            print(f"  Mean: {sts_stats.get('mean', 0):.4f}")
            print(f"  Std: {sts_stats.get('std', 0):.4f}")
            print(f"  Min: {sts_stats.get('min', 0):.4f}")
            print(f"  Max: {sts_stats.get('max', 0):.4f}")

        print("\n" + "=" * 60)
