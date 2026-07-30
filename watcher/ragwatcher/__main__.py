import argparse
import logging
import sys

from ragwatcher.config import WatcherConfig
from ragwatcher.core import scan_existing
from ragwatcher.state import StateCache
from ragwatcher.uploader import Uploader
from ragwatcher.watch import run


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser("ragwatcher",
                                     description="RagStarter folder watcher daemon")
    parser.add_argument("--once", action="store_true",
                        help="single catch-up scan, then exit (no watching)")
    args = parser.parse_args()

    config = WatcherConfig.from_env()
    if not config.api_key:
        print("RAGWATCH_API_KEY is required (create one in the admin dashboard)",
              file=sys.stderr)
        return 2
    if not config.watch_dir.is_dir():
        print(f"watch dir does not exist: {config.watch_dir}", file=sys.stderr)
        return 2

    if args.once:
        cache = StateCache(config.db_path)
        counts = scan_existing(config, cache, Uploader(config))
        print(counts)
        cache.close()
        return 0
    run(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
