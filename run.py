"""MC Builder entry point (run as script by PyInstaller)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcbuilder.app import main

if __name__ == "__main__":
    main()
