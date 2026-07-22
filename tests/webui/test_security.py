"""Adversarial regressions for the local Web UI trust boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui import app as webapp
from webui.security import RequestValidationError, resolve_data_file, validate_device


def _write_market_csv(path: Path, rows: int = 4) -> None:
    values = ["timestamps,open,high,low,close,volume"]
    for index in range(rows):
        price = 100 + index
        values.append(
            f"2025-01-{index + 1:02d}T00:00:00Z,"
            f"{price},{price + 2},{price - 1},{price + 1},1000"
        )
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(webapp, "DATA_DIR", tmp_path)
    monkeypatch.setattr(webapp, "MAX_DATA_FILE_BYTES", 1024 * 1024)
    monkeypatch.setattr(webapp, "MAX_DATA_ROWS", 1000)
    monkeypatch.setattr(webapp, "predictor", None)
    webapp.app.config.update(
        TESTING=True,
        MAX_CONTENT_LENGTH=64 * 1024,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    with webapp.app.test_client() as test_client:
        yield test_client


def test_data_listing_exposes_identifier_not_absolute_path(client, tmp_path: Path) -> None:
    _write_market_csv(tmp_path / "sample.csv")

    response = client.get("/api/data-files")

    assert response.status_code == 200
    listing = response.get_json()
    assert len(listing) == 1
    assert listing[0]["name"] == "sample.csv"
    assert listing[0]["path"] == "sample.csv"
    assert listing[0]["size"].endswith(" KB")
    assert str(tmp_path) not in response.get_data(as_text=True)


def test_selected_file_loads_only_from_configured_data_directory(client, tmp_path: Path) -> None:
    _write_market_csv(tmp_path / "sample.csv")

    response = client.post("/api/load-data", json={"file_path": "sample.csv"})

    assert response.status_code == 200
    assert response.get_json()["data_info"]["rows"] == 4


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            "timestamps,open,high,low,close\n",
            "Selected data file contains no rows",
        ),
        (
            "open,high,low,close\n100,102,99,101\n",
            "Missing required timestamp column",
        ),
        (
            "timestamps,date,open,high,low,close\n"
            "2025-01-01T00:00:00Z,2025-01-01,100,102,99,101\n",
            "Multiple timestamp columns are ambiguous",
        ),
        (
            "timestamps,open,high,low,close\nnot-a-date,100,102,99,101\n",
            "Timestamp column contains invalid values",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-01T00:00:00Z,100,102,99,101\n"
            "2025-01-01T00:00:00Z,101,103,100,102\n",
            "Timestamp column contains duplicates",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-02T00:00:00Z,100,102,99,101\n"
            "2025-01-01T00:00:00Z,101,103,100,102\n",
            "Timestamp column must be strictly increasing",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-01T00:00:00Z,100,bad,99,101\n",
            "Market data contains missing or non-finite numeric values",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-01T00:00:00Z,100,inf,99,101\n",
            "Market data contains missing or non-finite numeric values",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-01T00:00:00Z,0,102,0,101\n",
            "Market prices must be positive",
        ),
        (
            "timestamps,open,high,low,close\n"
            "2025-01-01T00:00:00Z,100,100,99,101\n",
            "Market data contains invalid OHLC relationships",
        ),
        (
            "timestamps,open,high,low,close,volume\n"
            "2025-01-01T00:00:00Z,100,102,99,101,-1\n",
            "volume must be non-negative",
        ),
        (
            "timestamps,open,high,low,close,amount\n"
            "2025-01-01T00:00:00Z,100,102,99,101,-1\n",
            "amount must be non-negative",
        ),
    ],
)
def test_market_data_validation_fails_closed(
    client,
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    (tmp_path / "invalid.csv").write_text(content, encoding="utf-8")

    response = client.post("/api/load-data", json={"file_path": "invalid.csv"})

    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_invalid_rows_are_not_silently_removed(client, tmp_path: Path) -> None:
    (tmp_path / "mixed.csv").write_text(
        "timestamps,open,high,low,close\n"
        "2025-01-01T00:00:00Z,100,102,99,101\n"
        "2025-01-02T00:00:00Z,101,not-a-number,100,102\n",
        encoding="utf-8",
    )

    response = client.post("/api/load-data", json={"file_path": "mixed.csv"})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Market data contains missing or non-finite numeric values"
    }


@pytest.mark.parametrize(
    "identifier",
    ["../outside.csv", "/tmp/outside.csv", r"..\outside.csv", "nested/sample.csv"],
)
def test_path_traversal_and_absolute_paths_are_rejected(
    client,
    identifier: str,
) -> None:
    response = client.post("/api/load-data", json={"file_path": identifier})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid data file identifier"}


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside = tmp_path / "outside.csv"
    _write_market_csv(outside)
    (data_dir / "escape.csv").symlink_to(outside)

    with pytest.raises(RequestValidationError, match="unavailable"):
        resolve_data_file(data_dir, "escape.csv", 1024 * 1024)


def test_undeclared_data_format_is_rejected(tmp_path: Path) -> None:
    data_file = tmp_path / "sample.feather"
    data_file.write_bytes(b"not-a-supported-parser-input")

    with pytest.raises(RequestValidationError, match="unavailable"):
        resolve_data_file(tmp_path, data_file.name, 1024 * 1024)


def test_oversized_files_are_hidden_and_rejected(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized = tmp_path / "oversized.csv"
    oversized.write_bytes(b"x" * 32)
    monkeypatch.setattr(webapp, "MAX_DATA_FILE_BYTES", 16)

    assert client.get("/api/data-files").get_json() == []
    response = client.post("/api/load-data", json={"file_path": "oversized.csv"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Selected data file exceeds the local size limit"}


def test_json_object_is_required(client) -> None:
    wrong_media = client.post(
        "/api/load-data",
        data="{}",
        content_type="text/plain",
    )
    wrong_shape = client.post("/api/load-data", json=["sample.csv"])

    assert wrong_media.status_code == 400
    assert wrong_media.get_json() == {"error": "Request body must use application/json"}
    assert wrong_shape.status_code == 400
    assert wrong_shape.get_json() == {"error": "Request body must be a JSON object"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("lookback", 0, "lookback must be between 1 and 2048"),
        ("pred_len", 513, "pred_len must be between 1 and 512"),
        ("sample_count", 6, "sample_count must be between 1 and 5"),
        ("temperature", 2.1, "temperature must be between 0.1 and 2.0"),
        ("top_p", 0.0, "top_p must be between 0.1 and 1.0"),
        ("lookback", True, "lookback must be an integer"),
    ],
)
def test_prediction_parameters_are_bounded(
    client,
    field: str,
    value: object,
    message: str,
) -> None:
    payload = {"file_path": "sample.csv", field: value}

    response = client.post("/api/predict", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_model_device_is_allowlisted(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webapp, "MODEL_AVAILABLE", True)

    response = client.post(
        "/api/load-model",
        json={"model_key": "kronos-small", "device": "cuda:../../etc/passwd"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Unsupported model device"}
    assert validate_device("cpu") == "cpu"


def test_cross_origin_mutation_is_rejected(client) -> None:
    response = client.post(
        "/api/load-data",
        json={"file_path": "sample.csv"},
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Cross-origin API requests are not allowed"}
    assert "Access-Control-Allow-Origin" not in response.headers


def test_api_responses_have_security_headers_and_no_cors(client) -> None:
    response = client.get("/api/available-models")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in response.headers


def test_request_body_limit_fails_closed(client) -> None:
    webapp.app.config["MAX_CONTENT_LENGTH"] = 32

    response = client.post(
        "/api/load-data",
        data='{"file_path":"' + ("x" * 128) + '"}',
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "Request body exceeds the local size limit"}


def test_internal_exception_text_is_not_returned(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_load(_file_path: object):
        raise RuntimeError("sensitive-local-path-and-token")

    monkeypatch.setattr(webapp, "load_data_file", fail_load)

    response = client.post("/api/load-data", json={"file_path": "sample.csv"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to load selected data"}
    assert "sensitive-local-path-and-token" not in response.get_data(as_text=True)


def test_untrusted_host_is_rejected(client) -> None:
    response = client.get("/api/data-files", base_url="http://attacker.example")

    assert response.status_code == 400


def test_launchers_do_not_install_or_expose_debug_server() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    launcher = (project_root / "webui" / "run.py").read_text(encoding="utf-8")
    shell_launcher = (project_root / "webui" / "start.sh").read_text(encoding="utf-8")
    application = (project_root / "webui" / "app.py").read_text(encoding="utf-8")
    template = (project_root / "webui" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    combined = launcher + shell_launcher + application
    assert "debug=True" not in combined
    assert "host='0.0.0.0'" not in combined
    assert 'host="0.0.0.0"' not in combined
    assert "pip3 install" not in shell_launcher
    assert "plotly-latest" not in template
    assert "npm/axios/dist" not in template
    assert "plotly-2.26.0.min.js" in template
    assert "axios@1.18.1/dist/axios.min.js" in template
    assert template.count('integrity="sha384-') == 2
    assert template.count('crossorigin="anonymous"') == 2


def test_generated_prediction_results_are_ignored() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    ignore_rules = (project_root / ".gitignore").read_text(encoding="utf-8")

    assert "webui/prediction_results/" in ignore_rules.splitlines()
