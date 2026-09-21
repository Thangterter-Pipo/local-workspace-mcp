"""Load .env next to this script so Local Workspace MCP picks up its settings."""
import os
import sys
from pathlib import Path

# Prevent system/user PYTHONPATH (e.g. hermes-agent) from polluting this venv
os.environ.pop("PYTHONPATH", None)
sys.path = [p for p in sys.path if "hermes-agent" not in p]

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from server import main  # noqa: E402

if __name__ == "__main__":
    main()
