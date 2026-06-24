"""Tests for core errors and logging (Build Queue v2.1 Task 77)."""

from __future__ import annotations

import logging

import pytest

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.core import (
    AnalyticsPlatformError,
    ContractError,
    StageError,
    configure_logging,
    get_logger,
    log_stage_failure,
)


class TestExceptions:
    def test_base_error_message(self) -> None:
        e = AnalyticsPlatformError("boom")
        assert e.message == "boom"
        assert e.context == {}
        assert str(e) == "boom"

    def test_base_error_with_context(self) -> None:
        e = AnalyticsPlatformError("boom", context={"k": "v"})
        assert e.context == {"k": "v"}

    def test_stage_error_carries_issue(self) -> None:
        issue = Issue(
            code="X", severity=Severity.ERROR, message="m"
        )
        e = StageError("stage failed", issue=issue, stage_id="s1", run_id="r1")
        assert e.issue is issue
        assert e.stage_id == "s1"
        assert e.run_id == "r1"
        assert isinstance(e, AnalyticsPlatformError)

    def test_contract_error_carries_issue(self) -> None:
        issue = Issue(
            code="X", severity=Severity.ERROR, message="m"
        )
        e = ContractError("contract failed", issue=issue)
        assert e.issue is issue
        assert isinstance(e, AnalyticsPlatformError)

    def test_stage_error_raises(self) -> None:
        issue = Issue(
            code="X", severity=Severity.ERROR, message="m"
        )
        with pytest.raises(StageError) as ei:
            raise StageError("fail", issue=issue, stage_id="s1")
        assert ei.value.stage_id == "s1"


class TestLogger:
    def test_get_logger_default(self) -> None:
        logger = get_logger()
        assert logger.name == "analytics_platform"

    def test_get_logger_with_name(self) -> None:
        logger = get_logger("foo.bar")
        assert logger.name == "analytics_platform.foo.bar"

    def test_get_logger_with_namespace_preserved(self) -> None:
        logger = get_logger("analytics_platform.custom")
        assert logger.name == "analytics_platform.custom"

    def test_get_logger_is_caching(self) -> None:
        a = get_logger("x")
        b = get_logger("x")
        assert a is b

    def test_configure_logging(self) -> None:
        configure_logging(level=logging.WARNING)
        logger = get_logger()
        assert logger.level == logging.WARNING

    def test_log_stage_failure_emits_warning(self, caplog) -> None:
        # Use a fresh logger (not the namespace root that other
        # tests may have configured) to avoid handler issues.
        logger = get_logger("test_log_stage_failure")
        issue = Issue(
            code="SCHEMA_MISMATCH", severity=Severity.ERROR, message="m"
        )
        exc = StageError("stage failed", issue=issue, stage_id="s1", run_id="r1")
        with caplog.at_level(logging.WARNING, logger=logger.name):
            log_stage_failure(logger, exc)
        # Verify the record was emitted at WARNING with the
        # expected code/severity in ``extra``.
        matching = [
            r for r in caplog.records
            if r.name == logger.name and r.levelno == logging.WARNING
        ]
        assert matching, f"no WARNING record found for {logger.name}"
        record = matching[0]
        # ``extra`` is exposed as attributes on the record.
        assert getattr(record, "issue_code", None) == "SCHEMA_MISMATCH"
        assert getattr(record, "stage_id", None) == "s1"
