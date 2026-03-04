import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseState:
    """
    Manages SQLite database state for tracking availability diffs.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS availability_slots (
                    id TEXT PRIMARY KEY,
                    date TEXT,
                    time TEXT,
                    party_size INTEGER,
                    status TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def process_snapshot(
        self, date_str: str, party_size: int, incoming_slots: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """
        Process incoming slots to detect newly added availability.
        Returns: (added_slots, removed_slots)
        """
        # Very simple naive diff engine for the scaffolding
        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []

        def _slot_time(s: dict) -> str:
            return s.get("time", s.get("start_time", "unknown"))

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM availability_slots WHERE date=? AND party_size=?",
                (date_str, party_size),
            )
            existing_rows = await cursor.fetchall()
            existing_ids = {row["id"] for row in existing_rows}

            incoming_ids = {
                str(s.get("id", f"{date_str}_{_slot_time(s)}")) for s in incoming_slots
            }

            new_ids = incoming_ids - existing_ids
            # missing_ids = existing_ids - incoming_ids # optionally track what got booked

            for s in incoming_slots:
                slot_id = str(s.get("id", f"{date_str}_{_slot_time(s)}"))
                if slot_id in new_ids:
                    added.append(s)
                    await db.execute(
                        """
                        INSERT INTO availability_slots (id, date, time, party_size, status)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (slot_id, date_str, _slot_time(s), party_size, "AVAILABLE"),
                    )

            await db.commit()

        return added, removed
