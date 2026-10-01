from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DataAgentError(RuntimeError):
    """Raised when data agent operations fail."""


class DataAgent:
    """Data Agent for processing CrowdWisdom data files."""

    def __init__(self, *, data_dir: str = "data/unique_data", processed_dir: str = "data/processed") -> None:
        self.data_dir = Path(data_dir)
        self.processed_dir = Path(processed_dir)

    def _inspect_directory(self) -> list[Path]:
        """Inspect the data directory for supported file types."""
        if not self.data_dir.exists():
            raise DataAgentError(f"Data directory does not exist: {self.data_dir}")

        supported_files = []
        for path in self.data_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {".csv", ".json", ".parquet", ".xlsx"}:
                supported_files.append(path)
        return sorted(supported_files)

    def _read_file(self, path: Path) -> Any:
        """Read a data file based on its extension."""
        suffix = path.suffix.lower()
        with path.open("r", encoding="utf-8") as f:
            if suffix == ".csv":
                return list(csv.DictReader(f))
            if suffix == ".json":
                data = json.load(f)
                if isinstance(data, dict) and "records" in data and isinstance(data["records"], list):
                    return data["records"]
                return data
            if suffix in {".parquet", ".xlsx"}:
                raise DataAgentError(
                    f"Unsupported file type for direct read: {path.suffix}. "
                    f"Install pandas with pyarrow for {path.suffix} support."
                )
        raise DataAgentError(f"Unsupported file type: {path.suffix}")

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a record for consistent field names."""
        normalized = {}
        for key, value in record.items():
            normalized_key = key.strip().lower().replace(" ", "_").replace("-", "_")
            normalized[normalized_key] = value
        return normalized

    def _safe_summary(self, records: list[dict[str, Any]], source_file: str) -> dict[str, Any]:
        """Create safe, privacy-conscious summaries of processed data."""
        if not records:
            return {
                "source_file": source_file,
                "record_count": 0,
                "field_names": [],
                "notes": ["No records found in source file."],
            }

        field_names = sorted({key for record in records for key in record.keys()})
        return {
            "source_file": source_file,
            "record_count": len(records),
            "field_names": field_names,
            "notes": ["Summary is derived from source data. No personal identifiers are included."],
        }

    def _build_data_dictionary(self, file_summaries: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a data dictionary from processed file summaries."""
        all_fields: dict[str, dict[str, Any]] = {}
        for summary in file_summaries:
            for field in summary.get("field_names", []):
                all_fields[field] = {
                    "source_file": summary["source_file"],
                    "present": True,
                    "record_count": summary["record_count"],
                }

        return {
            "data_dictionary_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_directory": str(self.data_dir),
                "file_count": len(file_summaries),
                "total_records": sum(s.get("record_count", 0) for s in file_summaries),
            },
            "fields": all_fields,
        }

    def run(self) -> dict[str, Any]:
        """Execute the data agent workflow."""
        logger.info("Starting Data Agent")

        # Inspect data directory
        supported_files = self._inspect_directory()
        logger.info("Found %d supported data files", len(supported_files))

        # Process each file
        processed_records: list[dict[str, Any]] = []
        file_summaries: list[dict[str, Any]] = []

        for path in supported_files:
            logger.info("Processing %s", path)
            try:
                records = self._read_file(path)
                if not isinstance(records, list):
                    raise DataAgentError(f"Expected a list of records in {path}")

                normalized_records = [
                    {
                        "source_file": str(path),
                        "record": record,
                        "normalized": self._normalize_record(record) if isinstance(record, dict) else record,
                    }
                    for record in records
                    if isinstance(record, dict)
                ]
                processed_records.extend(normalized_records)

                file_summaries.append(self._safe_summary(records, str(path)))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to process %s: %s", path, exc)
                file_summaries.append(
                    {
                        "source_file": str(path),
                        "record_count": 0,
                        "field_names": [],
                        "notes": [f"Processing failed: {exc}"],
                    }
                )

        # Save processed unique data
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        unique_data_path = self.processed_dir / "unique_data.json"
        unique_data = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_directory": str(self.data_dir),
                "file_count": len(supported_files),
                "total_records": len(processed_records),
                "status": "completed" if supported_files else "no_data_available",
            },
            "records": processed_records,
        }
        unique_data["unique_data_available"] = bool(supported_files)
        with unique_data_path.open("w", encoding="utf-8") as f:
            json.dump(unique_data, f, indent=2, ensure_ascii=False)

        # Save data dictionary
        data_dictionary = self._build_data_dictionary(file_summaries)
        with unique_data_path.with_name("data_dictionary.json").open("w", encoding="utf-8") as f:
            json.dump(data_dictionary, f, indent=2, ensure_ascii=False)

        unique_data["unique_data_available"] = bool(supported_files)
        logger.info("Data Agent completed. Outputs written to %s and %s", unique_data_path, unique_data_path.with_name("data_dictionary.json"))
        return unique_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = DataAgent()
    result = agent.run()
    print(f"Data processing completed with {result['metadata']['total_records']} total records")