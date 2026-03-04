#!/usr/bin/env python3
import argparse
import logging
from core.bot import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="lobster-bot")
    parser.add_argument(
        "--data-dir",
        help="Separate directory for Claude Code to work in (copies CLAUDE.md, .claude/, .mcp.json there). "
             "Useful for testing without modifying the source repo.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    main(data_dir=args.data_dir)
