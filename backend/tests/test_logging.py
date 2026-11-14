import json
import logging

from backend.app.observability import JSONFormatter


def test_logs_are_json_and_do_not_include_exception_details():
    try:
        raise ValueError("postgresql://private-password")
    except ValueError:
        import sys
        record = logging.LogRecord("test", logging.ERROR, "", 0, "job_failed", (), sys.exc_info())
    record.job_id = "example"
    result = json.loads(JSONFormatter().format(record))
    assert result["message"] == "job_failed"
    assert result["job_id"] == "example"
    assert result["error_type"] == "ValueError"
    assert "private-password" not in json.dumps(result)
