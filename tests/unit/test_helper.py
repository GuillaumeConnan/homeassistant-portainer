"""Unit tests for the Portainer helper module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from custom_components.portainer.helper import (
    as_local,
    format_attribute,
    format_camel_case,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("test_attribute", "Test attribute"),
        ("test-attribute-name", "Test attribute name"),
        ("", ""),
        ("_test", " test"),
        ("test__attribute", "Test  attribute"),
        ("CPU_USAGE", "Cpu usage"),
        ("test_ünicöde", "Test ünicöde"),
    ],
)
def test_format_attribute_preserves_legacy_separator_format(value, expected):
    """Replace supported separators and capitalize the resulting string."""
    assert format_attribute(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("test_attribute", "Testattribute"),
        ("test-attribute-name", "Testattributename"),
        ("Test_Attribute_Name", "Testattributename"),
        ("", ""),
        ("_test_attribute", "testattribute"),
        ("test__attribute--name", "Testattributename"),
    ],
)
def test_format_camel_case_preserves_legacy_format(value, expected):
    """Remove formatted spaces after capitalizing the complete attribute."""
    assert format_camel_case(value) == expected


def test_as_local_keeps_datetime_when_timezone_is_unspecified():
    """An unset local timezone uses the system timezone conversion."""
    aware = datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc)

    with patch("custom_components.portainer.helper.DEFAULT_TIME_ZONE", None):
        result = as_local(aware)

    assert result.timestamp() == aware.timestamp()


def test_as_local_localizes_naive_datetime_as_utc():
    """Naive input is treated as UTC before local timezone conversion."""
    naive = datetime(2021, 1, 1, 12, 0)

    with patch("custom_components.portainer.helper.DEFAULT_TIME_ZONE", timezone.utc):
        result = as_local(naive)

    assert result == naive.replace(tzinfo=timezone.utc)


def test_as_local_converts_to_configured_timezone():
    """Aware UTC datetimes are converted to the configured timezone."""
    utc_datetime = datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc)
    local_timezone = timezone(timedelta(hours=-5))

    with patch("custom_components.portainer.helper.DEFAULT_TIME_ZONE", local_timezone):
        result = as_local(utc_datetime)

    assert result.hour == 7
    assert result.tzinfo == local_timezone


def test_as_local_rejects_none():
    """Invalid non-datetime input raises rather than being silently accepted."""
    with patch("custom_components.portainer.helper.DEFAULT_TIME_ZONE", None):
        with pytest.raises(AttributeError):
            as_local(None)
