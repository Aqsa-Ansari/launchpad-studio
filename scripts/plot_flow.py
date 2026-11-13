"""Draw the flow diagram to an interactive HTML file:  python scripts/plot_flow.py"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from launchpad.config import OUTPUT_DIR  # noqa: E402
from launchpad.flow import LaunchFlow  # noqa: E402

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    produced = LaunchFlow(suppress_flow_events=True).plot("launch_flow.html", show=False)
    src = Path(produced)
    # plot() may emit helper .js/.css files next to the html; copy them all together
    for f in src.parent.glob(f"{src.stem}*"):
        if f.is_file():
            shutil.copy(f, OUTPUT_DIR / f.name)
    print("Wrote", OUTPUT_DIR / src.name)
