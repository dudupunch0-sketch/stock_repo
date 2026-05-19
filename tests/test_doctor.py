from stock_agents.doctor import check_hermes_installation, run_doctor


def test_check_hermes_installation_reports_missing_binary():
    status = check_hermes_installation(executable="definitely-not-a-real-hermes-binary")

    assert status.name == "hermes"
    assert status.ok is False
    assert "not found" in status.message


def test_run_doctor_includes_mock_runner_without_external_llm():
    report = run_doctor(smoke_runner="mock")

    assert "mock runner: ok" in report
    assert "Hermes" in report
