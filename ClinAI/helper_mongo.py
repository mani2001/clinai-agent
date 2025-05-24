"""
MongoDB helper functions for storing clinical conversations **and notes**.
This module provides CRUD helpers for patient‑specific clinical data.
Each document now *must* contain three required keys:
    - `patient_id`  : unique identifier (taken from the dataset's `idx`)
    - `conversation`: raw dialogue transcript
    - `note`        : associated clinician note

Environment variables expected (see .env):
    ATLAS_URI          : full MongoDB Atlas connection string
    MONGODB_PASSWORD   : optional, only needed if ATLAS_URI contains the
                         <password> placeholder
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import pymongo
from dotenv import load_dotenv
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Environment & logging setup
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MongoDBHelper:
    """Light wrapper around a single MongoDB collection."""

    # ---------------------------------------------------------------------
    # Construction / connection
    # ---------------------------------------------------------------------
    def __init__(
        self,
        connection_string: str | None = None,
        database_name: str = "clinical_data",
        collection_name: str = "patient_records",
    ) -> None:
        # Resolve connection string  --------------------------------------
        if connection_string is None:
            connection_string = os.getenv("ATLAS_URI")
            if not connection_string:
                raise ValueError(
                    "MongoDB connection string not found. Set ATLAS_URI in .env "
                    "or pass connection_string explicitly."
                )

            # Replace <password> token if present -------------------------
            if "<password>" in connection_string:
                pwd = os.getenv("MONGODB_PASSWORD")
                if not pwd:
                    raise ValueError(
                        "ATLAS_URI contains <password> but MONGODB_PASSWORD not set"
                    )
                connection_string = connection_string.replace("<password>", pwd)

            logger.info("Using connection string from ATLAS_URI env var")
        else:
            logger.info("Using provided connection string")

        # Connect ---------------------------------------------------------
        try:
            self.client: MongoClient = MongoClient(connection_string)
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
            logger.info(f"Connected to MongoDB: {database_name}.{collection_name}")

            # Unique index on patient_id for O(1) look‑ups ----------------
            self.collection.create_index("patient_id", unique=True)
        except pymongo.errors.ConnectionFailure as exc:
            logger.error("Could not connect to MongoDB", exc_info=exc)
            raise

    # ---------------------------------------------------------------------
    # Insertion helpers
    # ---------------------------------------------------------------------
    _REQUIRED_FIELDS = {"patient_id", "conversation", "note"}

    def _validate_doc(self, doc: Dict[str, Any]) -> None:
        missing = self._REQUIRED_FIELDS - doc.keys()
        if missing:
            raise ValueError(f"Document missing required fields: {missing}")

    def add_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """Insert a single patient record."""
        self._validate_doc(conversation_data)
        try:
            result = self.collection.insert_one(conversation_data)
            logger.info("Added record for patient ID %s", conversation_data["patient_id"])
            return str(result.inserted_id)
        except pymongo.errors.DuplicateKeyError as exc:
            logger.error("Duplicate patient_id %s", conversation_data["patient_id"])
            raise exc

    def add_many_conversations(self, conversations: List[Dict[str, Any]]) -> int:
        """Bulk‑insert multiple patient records."""
        for conv in conversations:
            self._validate_doc(conv)
        try:
            result = self.collection.insert_many(conversations, ordered=False)
            logger.info("Inserted %d records", len(result.inserted_ids))
            return len(result.inserted_ids)
        except pymongo.errors.BulkWriteError as exc:
            logger.warning("Bulk insert completed with errors: %s", exc.details)
            return exc.details.get("nInserted", 0)

    # ---------------------------------------------------------------------
    # Retrieval helpers
    # ---------------------------------------------------------------------
    def get_conversation(self, patient_id: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"patient_id": patient_id}, {"_id": 0})
        logger.info("%sfound record for patient ID %s", "" if doc else "No ", patient_id)
        return doc

    def get_conversations(
        self,
        query: Dict[str, Any] | None = None,
        limit: int = 100,
        skip: int = 0,
        sort_by: str = "patient_id",
        sort_order: int = pymongo.ASCENDING,
    ) -> List[Dict[str, Any]]:
        query = query or {}
        cursor = (
            self.collection.find(query, {"_id": 0})
            .sort(sort_by, sort_order)
            .skip(skip)
            .limit(limit)
        )
        results = list(cursor)
        logger.info("Retrieved %d records", len(results))
        return results

    # ---------------------------------------------------------------------
    # Update / delete helpers
    # ---------------------------------------------------------------------
    def update_conversation(self, patient_id: str, updates: Dict[str, Any]) -> bool:
        if "patient_id" in updates:
            logger.warning("Cannot modify patient_id; ignoring field in updates")
            updates.pop("patient_id")
        if not updates:
            logger.info("No updatable fields provided for patient %s", patient_id)
            return False
        res = self.collection.update_one({"patient_id": patient_id}, {"$set": updates})
        logger.info("Updated %d record(s) for patient %s", res.modified_count, patient_id)
        return res.modified_count > 0

    def delete_conversation(self, patient_id: str) -> bool:
        res = self.collection.delete_one({"patient_id": patient_id})
        logger.info("Deleted %d record(s) for patient %s", res.deleted_count, patient_id)
        return res.deleted_count > 0

    def delete_conversations(self, query: Dict[str, Any]) -> int:
        res = self.collection.delete_many(query)
        logger.info("Deleted %d records", res.deleted_count)
        return res.deleted_count

    # ---------------------------------------------------------------------
    # Misc helpers
    # ---------------------------------------------------------------------
    def count_conversations(self, query: Dict[str, Any] | None = None) -> int:
        query = query or {}
        count = self.collection.count_documents(query)
        logger.info("Counted %d matching records", count)
        return count

    def search_conversations(
        self,
        text_query: str,
        fields: List[str] | None = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if fields is None:
            fields = ["conversation", "note"]
        or_clauses = [{field: {"$regex": text_query, "$options": "i"}} for field in fields]
        results = list(self.collection.find({"$or": or_clauses}, {"_id": 0}).limit(limit))
        logger.info("Search returned %d records for query '%s'", len(results), text_query)
        return results

    # ---------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------
    def close(self) -> None:
        if hasattr(self, "client"):
            self.client.close()
            logger.info("MongoDB connection closed")
