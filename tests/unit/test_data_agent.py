from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agents.data_agent import DataAgent


@pytest.fixture
def data_agent(tmp_path: Path):
    return DataAgent(
        data_dir=str(tmp_path / "data" / "unique_data"),
        processed_dir=str(tmp_path / "data" / "processed"),
    )


def test_data_agent_initialization(data_agent, tmp_path: Path):
    """Test that DataAgent initializes with correct paths."""
    assert data_agent.data_dir == tmp_path / "data" / "unique_data"
    assert data_agent.processed_dir == tmp_path / "data" / "processed"


def test_data_agent_inspect_directory_empty(data_agent, tmp_path: Path):
    """Test inspecting an empty data directory."""
    data_dir = tmp_path / "data" / "unique_data"
    data_dir.mkdir(parents=True)

    supported_files = data_agent._inspect_directory()
    assert supported_files == []


def test_data_agent_inspect_directory_with_files(data_agent, tmp_path: Path):
    """Test inspecting a data directory with supported files."""
    data_dir = tmp_path / "data" / "unique_data"
    data_dir.mkdir(parents=True)

    # Create sample files
    (data_dir / "test.csv").write_text("name,age\nAlice,30\nBob,25\n")
    (data_dir / "test.json").write_text('[{"name": "Alice", "age": 30}]')
    (data_dir / "test.parquet").write_text("not a real parquet")  # Will be detected but fail to read

    supported_files = data_agent._inspect_directory()
    assert len(supported_files) == 3
    assert all(p.suffix in {".csv", ".json", ".parquet"} for p in supported_files)


def test_data_agent_read_csv_file(data_agent, tmp_path: Path):
    """Test reading a CSV file."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("name,age\nAlice,30\nBob,25\n")

    records = data_agent._read_file(csv_path)
    assert len(records) == 2
    assert records[0] == {"name": "Alice", "age": "30"}
    assert records[1] == {"name": "Bob", "age": "25"}


def test_data_agent_read_json_file(data_agent, tmp_path: Path):
    """Test reading a JSON file."""
    json_path = tmp_path / "test.json"
    json_path.write_text('[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')

    records = data_agent._read_file(json_path)
    assert len(records) == 2
    assert records[0] == {"name": "Alice", "age": 30}
    assert records[1] == {"name": "Bob", "age": 25}


def test_data_agent_read_unsupported_file_type(data_agent, tmp_path: Path):
    """Test that reading an unsupported file type raises an error."""
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("not a data file")

    with pytest.raises(Exception, match="Unsupported file type"):
        data_agent._read_file(txt_path)


def test_data_agent_read_csv_with_missing_fields(data_agent, tmp_path: Path):
    """Test reading CSV where some fields may be empty."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("name,age,city\nAlice,30,New York\nBob,25,\n")

    records = data_agent._read_file(csv_path)
    assert len(records) == 2
    assert records[0] == {"name": "Alice", "age": "30", "city": "New York"}
    assert records[1] == {"name": "Bob", "age": "25", "city": ""}


def test_data_agent_normalize_record():
    """Test record normalization."""
    agent = DataAgent(data_dir="data/unique_data", processed_dir="data/processed")
    raw_record = {"First Name": "Alice", "Last Name": "Smith", "Age-Years": 30}
    normalized = agent._normalize_record(raw_record)
    assert normalized == {"first_name": "Alice", "last_name": "Smith", "age_years": 30}


def test_data_agent_safe_summary_empty():
    """Test safe summary with empty records."""
    agent = DataAgent(data_dir="data/unique_data", processed_dir="data/processed")
    summary = agent._safe_summary([], "test.csv")
    assert summary["source_file"] == "test.csv"
    assert summary["record_count"] == 0
    assert summary["field_names"] == []
    assert "No records found" in summary["notes"][0]


def test_data_agent_safe_summary_with_records():
    """Test safe summary with records."""
    agent = DataAgent(data_dir="data/unique_data", processed_dir="data/processed")
    records = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    summary = agent._safe_summary(records, "test.csv")
    assert summary["source_file"] == "test.csv"
    assert summary["record_count"] == 2
    assert sorted(summary["field_names"]) == ["age", "name"]


def test_data_agent_build_data_dictionary():
    """Test building a data dictionary from file summaries."""
    agent = DataAgent(data_dir="data/unique_data", processed_dir="data/processed")
    file_summaries = [
        {
            "source_file": "test.csv",
            "record_count": 10,
            "field_names": ["name", "age"],
        },
        {
            "source_file": "extra.csv",
            "record_count": 5,
            "field_names": ["name", "city"],
        },
    ]
    dictionary = agent._build_data_dictionary(file_summaries)
    assert "data_dictionary_metadata" in dictionary
    assert dictionary["data_dictionary_metadata"]["file_count"] == 2
    assert dictionary["data_dictionary_metadata"]["total_records"] == 15
    assert "name" in dictionary["fields"]
    assert "age" in dictionary["fields"]
    assert "city" in dictionary["fields"]


def test_data_agent_build_data_dictionary_empty():
    """Test building a data dictionary with no file summaries."""
    agent = DataAgent(data_dir="data/unique_data", processed_dir="data/processed")
    dictionary = agent._build_data_dictionary([])
    assert "data_dictionary_metadata" in dictionary
    assert dictionary["data_dictionary_metadata"]["file_count"] == 0
    assert dictionary["data_dictionary_metadata"]["total_records"] == 0
    assert dictionary["fields"] == {}


def test_data_agent_run_success_csv(data_agent, tmp_path: Path):
    """Test successful execution of the data agent with CSV input."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create sample data file
    (data_dir / "test.csv").write_text("name,age\nAlice,30\nBob,25\n")

    # Run the agent
    result = data_agent.run()

    # Verify result structure
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 2
    assert result["metadata"]["status"] == "completed"

    # Verify output files were created
    unique_data_path = processed_dir / "unique_data.json"
    assert unique_data_path.exists()
    with unique_data_path.open("r", encoding="utf-8") as f:
        saved_result = json.load(f)
    assert saved_result == result

    # Verify data dictionary was created
    data_dict_path = processed_dir / "data_dictionary.json"
    assert data_dict_path.exists()
    with data_dict_path.open("r", encoding="utf-8") as f:
        data_dict = json.load(f)
    assert "fields" in data_dict
    assert "name" in data_dict["fields"]
    assert "age" in data_dict["fields"]


def test_data_agent_run_success_json(data_agent, tmp_path: Path):
    """Test successful execution of the data agent with JSON input."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create sample data file
    (data_dir / "test.json").write_text('[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')

    # Run the agent
    result = data_agent.run()

    # Verify result structure
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 2
    assert result["metadata"]["status"] == "completed"

    # Verify output files were created
    unique_data_path = processed_dir / "unique_data.json"
    assert unique_data_path.exists()
    with unique_data_path.open("r", encoding="utf-8") as f:
        saved_result = json.load(f)
    assert saved_result == result


def test_data_agent_run_no_data(data_agent, tmp_path: Path):
    """Test data agent with no data files (empty directory)."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Run the agent
    result = data_agent.run()

    # Verify result structure represents no data available
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 0
    assert result["metadata"]["file_count"] == 0
    assert result["metadata"]["status"] == "no_data_available"

    # Verify output files were created
    unique_data_path = processed_dir / "unique_data.json"
    assert unique_data_path.exists()
    with unique_data_path.open("r", encoding="utf-8") as f:
        saved_result = json.load(f)
    assert saved_result == result


def test_data_agent_run_handles_unsupported_files(data_agent, tmp_path: Path):
    """Test data agent handles unsupported file types gracefully."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create a supported file and an unsupported file
    (data_dir / "test.csv").write_text("name,age\nAlice,30\nBob,25\n")
    (data_dir / "test.txt").write_text("not a data file")

    # Run the agent
    result = data_agent.run()

    # Verify result structure
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 2
    assert result["metadata"]["status"] == "completed"

    # Verify output files were created
    unique_data_path = processed_dir / "unique_data.json"
    assert unique_data_path.exists()
    with unique_data_path.open("r", encoding="utf-8") as f:
        saved_result = json.load(f)
    assert saved_result == result

    # Verify data dictionary was created
    data_dict_path = processed_dir / "data_dictionary.json"
    assert data_dict_path.exists()
    with data_dict_path.open("r", encoding="utf-8") as f:
        data_dict = json.load(f)
    assert "fields" in data_dict
    assert "name" in data_dict["fields"]
    assert "age" in data_dict["fields"]


def test_data_agent_run_handles_parquet_failure(data_agent, tmp_path: Path):
    """Test data agent handles parquet file processing failure gracefully."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create a CSV and a fake parquet file
    (data_dir / "test.csv").write_text("name,age\nAlice,30\n")
    (data_dir / "fake.parquet").write_text("this is not a real parquet file")

    # Run the agent
    result = data_agent.run()

    # Verify result structure
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 1
    assert result["metadata"]["file_count"] == 2

    # Verify output files were created
    unique_data_path = processed_dir / "unique_data.json"
    assert unique_data_path.exists()
    with unique_data_path.open("r", encoding="utf-8") as f:
        saved_result = json.load(f)
    assert saved_result == result


def test_data_agent_missing_directory_raises_error(data_agent):
    """Test that missing data directory raises an error."""
    # Don't create the directory
    with pytest.raises(Exception, match="Data directory does not exist"):
        data_agent._inspect_directory()


def test_data_agent_provenance_in_records(data_agent, tmp_path: Path):
    """Test that processed records retain source file provenance."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create sample data file
    (data_dir / "test.csv").write_text("name,age\nAlice,30\nBob,25\n")

    # Run the agent
    result = data_agent.run()

    # Verify provenance in records
    for record in result["records"]:
        assert "source_file" in record
        assert "record" in record
        assert "normalized" in record

    # Verify source file is included
    assert any(r["source_file"].endswith("test.csv") for r in result["records"])


def test_data_agent_run_with_csv_and_json(data_agent, tmp_path: Path):
    """Test data agent with multiple supported file types."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Create multiple file types
    (data_dir / "data.csv").write_text("name,age\nAlice,30\nBob,25\n")
    (data_dir / "extra.json").write_text('[{"name": "Charlie", "age": 40}]')

    # Run the agent
    result = data_agent.run()

    # Verify result structure
    assert "metadata" in result
    assert result["metadata"]["total_records"] == 3
    assert result["metadata"]["file_count"] == 2
    assert result["metadata"]["status"] == "completed"

    # Verify both source files are in records
    source_files = {Path(r["source_file"]).name for r in result["records"]}
    assert "data.csv" in source_files
    assert "extra.json" in source_files


def test_data_agent_run_creates_output_directory(data_agent, tmp_path: Path):
    """Test that running the agent creates the processed directory if it doesn't exist."""
    # Setup directory structure
    data_dir = tmp_path / "data" / "unique_data"
    processed_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)

    # Verify processed directory doesn't exist yet
    assert not processed_dir.exists()

    # Run the agent
    result = data_agent.run()

    # Verify processed directory was created
    assert processed_dir.exists()
    assert (processed_dir / "unique_data.json").exists()
    assert (processed_dir / "data_dictionary.json").exists()
