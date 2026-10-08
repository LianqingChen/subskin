import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Private, reviewed RGB dataset tools; never auto-deploy models"
    )
    parser.add_argument("command", choices=["validate", "train", "evaluate"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--side", type=int, default=512)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    from ml.rgb_segmentation.dataset import validate_manifest

    if args.command == "validate":
        document = validate_manifest(args.manifest, args.allow_synthetic)
        print(
            json.dumps(
                {
                    "counts": document["counts"],
                    "subjects": document["subject_count"],
                    "manifest_sha256": document["manifest_sha256"],
                }
            )
        )
    else:
        if not args.output:
            parser.error("--output required")
        if args.command == "train":
            from ml.rgb_segmentation.train import train

            report = train(
                args.manifest, args.output, args.epochs, args.side, args.allow_synthetic
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "epochs": len(report["history"]),
                        "enabled": False,
                    }
                )
            )
        else:
            from ml.rgb_segmentation.evaluate import evaluate

            report = evaluate(
                args.manifest, args.weights, args.output, args.allow_synthetic
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "summary": report["summary"],
                        "deployment_approved": False,
                    }
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
