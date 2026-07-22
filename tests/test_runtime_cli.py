"""Local runtime commands must remain bounded and machine-readable."""

import json

import pytest

from kronos_runtime.cli import _benchmark, _write_report, build_parser, main
from kronos_runtime.device import device_report, resolve_device


def test_cpu_device_report_is_json_serializable() -> None:
    report = device_report("cpu")

    assert resolve_device("cpu").type == "cpu"
    assert report["selected_device"] == "cpu"
    assert report["accelerated"] is False
    assert isinstance(report["torch_meets_generic_security_floor"], bool)
    json.dumps(report)


def test_unknown_device_is_refused() -> None:
    with pytest.raises(ValueError, match="device must be"):
        resolve_device("radeon-magic")


def test_doctor_command_emits_json(capsys) -> None:
    assert main(["doctor", "--device", "cpu"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["selected_device"] == "cpu"


def test_reports_are_not_silently_overwritten(tmp_path) -> None:
    output = tmp_path / "runtime.json"
    _write_report({"passed": True}, output)

    with pytest.raises(FileExistsError):
        _write_report({"passed": False}, output)


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        ("--horizon", "513", "horizon must not exceed 512"),
        ("--samples", "21", "samples must not exceed 20"),
        ("--runs", "21", "runs must not exceed 20"),
    ],
)
def test_benchmark_limits_fail_before_checkpoint_download(
    argument, value, message
) -> None:
    args = build_parser().parse_args(
        ["benchmark", "--device", "cpu", argument, value]
    )

    with pytest.raises(ValueError, match=message):
        _benchmark(args)
