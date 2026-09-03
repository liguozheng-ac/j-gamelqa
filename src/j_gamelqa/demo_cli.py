"""Console entry point for the optional local Streamlit demo."""

import argparse
from importlib.util import find_spec
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the J-GameLQA local Streamlit demo."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Streamlit without opening a browser (useful for smoke tests).",
    )
    parser.add_argument("--port", type=int, help="Optional Streamlit server port.")
    args = parser.parse_args()

    if find_spec("streamlit") is None:
        print(
            'Streamlit is not installed. Install the demo extra with: '
            'python -m pip install -e ".[demo]"',
            file=sys.stderr,
        )
        return 1

    from streamlit.web import cli as streamlit_cli

    app_path = Path(__file__).with_name("demo_app.py").resolve()
    streamlit_args = ["streamlit", "run", str(app_path)]
    if args.headless:
        streamlit_args.append("--server.headless=true")
    if args.port is not None:
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        streamlit_args.append(f"--server.port={args.port}")
    sys.argv = streamlit_args
    return int(streamlit_cli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
