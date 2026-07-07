"""One-command rebuild of the whole intelligence pipeline."""
import subprocess
import os

HERE = os.path.dirname(os.path.abspath(__file__))
for step in ["ingest.py", "analyze.py", "validate.py", "build_report.py"]:
    print(f"\n=== {step} ===")
    subprocess.run(["python3", os.path.join(HERE, step)], check=True)
print("\nPipeline complete. Outputs in data/processed/ and output/.")
