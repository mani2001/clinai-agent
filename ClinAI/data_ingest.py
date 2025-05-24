"""
Temporary ingestion script for the AGBonnet/augmented-clinical-notes dataset.
This script downloads the dataset and stores **both** the `conversation` and
corresponding clinician `note` in MongoDB.

You can optionally cap the number of records to ingest with `--max-records`.

Usage examples
--------------
• Ingest only the first 2 000 rows (default):
    python ingest_dataset.py               

• Ingest at most 500 rows:
    python ingest_dataset.py --max-records 500

• Ingest the full dataset but use larger batch writes:
    python ingest_dataset.py --batch-size 500 --max-records -1

Prerequisites
-------------
• .env file with ATLAS_URI (and optionally MONGODB_PASSWORD)
• `pip install datasets pymongo python-dotenv tqdm`
"""

from __future__ import annotations

import argparse
import logging
from typing import Dict, List

from dotenv import load_dotenv
from datasets import load_dataset
from tqdm import tqdm

from helper_mongo import MongoDBHelper

# ---------------------------------------------------------------------------
# Env & logging setup
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ingestion logic
# ---------------------------------------------------------------------------

def ingest(batch_size: int, max_records: int) -> None:
    """Stream (up to) *max_records* examples into MongoDB."""

    # 1) Connect to MongoDB -------------------------------------------------
    mongo_helper = MongoDBHelper()

    try:
        # 2) Load dataset ---------------------------------------------------
        split_arg = "train" if max_records < 0 else f"train[:{max_records}]"
        logger.info("Loading split '%s' from dataset …", split_arg)
        ds = load_dataset("AGBonnet/augmented-clinical-notes", split=split_arg)
        total = len(ds)
        logger.info("Loaded %d records", total)

        # 3) Iterate & batch-insert ----------------------------------------
        batch: List[Dict[str, str]] = []
        inserted_total = 0

        for i, rec in enumerate(tqdm(ds, total=total, desc="Processing")):
            conversation = rec.get("conversation")
            note = rec.get("note") or rec.get("notes")
            idx = rec.get("idx")

            if conversation is None or note is None or idx is None:
                continue  # skip incomplete rows

            batch.append(
                {
                    "patient_id": str(idx),
                    "conversation": conversation,
                    "note": note,
                }
            )

            flush = len(batch) >= batch_size or i == total - 1
            if flush:
                try:
                    n_inserted = mongo_helper.add_many_conversations(batch)
                    inserted_total += n_inserted
                    logger.info("Batch inserted %d / %d docs", n_inserted, len(batch))
                except Exception as exc:
                    logger.error("Batch insert failed: %s", exc)
                finally:
                    batch = []

        logger.info("Ingestion complete → %d documents inserted", inserted_total)

    finally:
        mongo_helper.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest AGBonnet/augmented-clinical-notes into MongoDB",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents per bulk insert (default: 100)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=2000,
        help="Maximum number of rows to ingest (default: 2000, -1 for all)",
    )
    args = parser.parse_args()

    ingest(batch_size=args.batch_size, max_records=args.max_records)


if __name__ == "__main__":
    main()
