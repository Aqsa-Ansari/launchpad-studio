import os
import sys
from pathlib import Path

os.environ["LAUNCHPAD_MOCK"] = "1"
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.pop("TAVILY_API_KEY", None)
os.environ.pop("SERPER_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
