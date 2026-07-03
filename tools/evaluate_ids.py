"""
VERISYNTH — IDS Evaluation Tool
Command-line interface for post-simulation IDS evaluation.

Usage:
    python tools/evaluate_ids.py \
        --packets outputs/packets/v2x_packets_verisynth_baseline.jsonl \
        --alerts  outputs/logs/ids_alerts.jsonl \
        --events  outputs/logs/events_verisynth_baseline.jsonl \
        --training outputs/logs/ids_training.log \
        --output  outputs/evaluation/
"""

import argparse
import logging
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.ids.evaluator import IDSEvaluator

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("verisynth.evaluate_ids")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VERISYNTH IDS Evaluation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full evaluation with all logs
  python tools/evaluate_ids.py \\
      --packets outputs/packets/v2x_packets_verisynth_baseline.jsonl \\
      --alerts  outputs/logs/ids_alerts.jsonl \\
      --events  outputs/logs/events_verisynth_baseline.jsonl \\
      --training outputs/logs/ids_training.log

  # Quick evaluation without alert log (computes GT stats only)
  python tools/evaluate_ids.py \\
      --packets outputs/packets/v2x_packets_verisynth_baseline.jsonl
        """
    )

    parser.add_argument(
        "--packets",
        required = True,
        help     = "Path to V2X packet log JSONL file (ground truth)"
    )
    parser.add_argument(
        "--alerts",
        default  = "outputs/logs/ids_alerts.jsonl",
        help     = "Path to IDS alert log JSONL file"
    )
    parser.add_argument(
        "--events",
        default  = None,
        help     = "Path to event log JSONL file (for block/suppress stats)"
    )
    parser.add_argument(
        "--training",
        default  = None,
        help     = "Path to IDS training log file"
    )
    parser.add_argument(
        "--output",
        default  = "outputs/evaluation/",
        help     = "Output directory for evaluation reports"
    )
    parser.add_argument(
        "--max-records",
        type    = int,
        default = 0,
        help    = "Maximum packet records to load (0 = all)"
    )

    args = parser.parse_args()

    logger.info("VERISYNTH IDS Evaluation Tool")
    logger.info("Packets:  %s", args.packets)
    logger.info("Alerts:   %s", args.alerts)
    logger.info("Events:   %s", args.events)
    logger.info("Training: %s", args.training)
    logger.info("Output:   %s", args.output)

    evaluator = IDSEvaluator(output_dir=args.output)

    # Load data
    n_gt     = evaluator.load_packet_log(args.packets, max_records=args.max_records)
    n_alerts = evaluator.load_alert_log(args.alerts)

    if args.events:
        event_counts = evaluator.load_event_log(args.events)
        logger.info("Event counts: %s", event_counts)

    if n_gt == 0:
        logger.error("No ground truth records loaded. Check packet log path.")
        sys.exit(1)

    logger.info("Loaded %d GT records, %d alerts", n_gt, n_alerts)

    # Run full evaluation and export
    evaluator.export_all(
        packet_log_path   = args.packets,
        alert_log_path    = args.alerts,
        training_log_path = args.training,
    )

    logger.info("Evaluation complete. Reports in: %s", args.output)


if __name__ == "__main__":
    main()
