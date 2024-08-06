import unittest
import time
from unittest.mock import patch
import warnings

from fluxutils.decorators import (
    retry,
    retry_exponential_backoff,
    timeout,
    rate_limiter,
    trace,
    suppress_exceptions,
    deprecated,
    type_check,
    log_execution_time,
    cache,
    requires_permission,
    TimeoutError,
    RateLimitError,
    PermissionError,
)


class TestDecorators(unittest.TestCase):

    def test_retry(self):
        attempts = 0

        @retry(max_retries=3, delay=0.1)
        def flaky_function() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("Not ready yet")
            return "Success"

        result = flaky_function()
        self.assertEqual(result, "Success")
        self.assertEqual(attempts, 3)

        with self.assertRaises(ValueError):

            @retry(max_retries=2, delay=0.1)
            def always_fails() -> None:
                raise ValueError("Always fails")

            always_fails()

    def test_retry_exponential_backoff(self):
        attempts = 0

        @retry_exponential_backoff(max_retries=4, initial_delay=0.1)
        def flaky_function() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 4:
                raise ValueError("Not ready yet")
            return "Success"

        start_time = time.time()
        result = flaky_function()
        end_time = time.time()

        self.assertEqual(result, "Success")
        self.assertEqual(attempts, 4)
        self.assertGreater(end_time - start_time, 0.7)  # 0.1 + 0.2 + 0.4 = 0.7

    def test_timeout(self):
        @timeout(1)
        def quick_function() -> str:
            return "Quick"

        @timeout(1)
        def slow_function() -> None:
            time.sleep(2)

        self.assertEqual(quick_function(), "Quick")

        with self.assertRaises(TimeoutError):
            slow_function()

    def test_rate_limiter(self):
        call_count = 0

        @rate_limiter(calls=3, period=1, immediate_fail=True)
        def limited_function() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        for _ in range(3):
            limited_function()

        with self.assertRaises(RateLimitError):
            limited_function()

        time.sleep(1)
        self.assertEqual(limited_function(), 4)

    def test_trace(self):
        @trace
        def sample_function(x: int, y: str) -> str:
            return f"{y} {x}"

        with patch("builtins.print") as mock_print:
            result = sample_function(42, "Answer:")
            self.assertEqual(result, "Answer: 42")
            mock_print.assert_any_call("Calling sample_function(42, 'Answer:')")
            mock_print.assert_any_call("sample_function returned 'Answer: 42'")

    def test_suppress_exceptions(self):
        @suppress_exceptions
        def risky_function() -> None:
            raise ValueError("Oops")

        with patch("builtins.print") as mock_print:
            result = risky_function()
            self.assertIsNone(result)
            mock_print.assert_called_with(
                "Exception suppressed in risky_function: ValueError: Oops"
            )

    def test_deprecated(self):
        @deprecated
        def old_function() -> str:
            return "I'm old"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_function()
            self.assertEqual(result, "I'm old")
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))
            self.assertIn("old_function is deprecated", str(w[-1].message))

    def test_type_check(self):
        @type_check(arg_types=(int, str), return_type=str)
        def typed_function(x: int, y: str) -> str:
            return f"{y} {x}"

        self.assertEqual(typed_function(42, "Answer:"), "Answer: 42")

        with self.assertRaises(TypeError):
            typed_function("42", "Answer:")

        @type_check(arg_types=(int, str), return_type=int)
        def wrong_return_type(x: int, y: str) -> str:
            return f"{y} {x}"

        with self.assertRaises(TypeError):
            wrong_return_type(42, "Answer:")

    def test_log_execution_time(self):
        @log_execution_time
        def slow_function() -> None:
            time.sleep(0.1)

        with patch("builtins.print") as mock_print:
            slow_function()
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            self.assertIn("Execution time for slow_function:", call_args)
            self.assertGreater(float(call_args.split(": ")[1].split()[0]), 0.1)

    def test_cache(self):
        call_count = 0

        @cache
        def expensive_function(x: int, y: int) -> int:
            nonlocal call_count
            call_count += 1
            return x + y

        self.assertEqual(expensive_function(2, 3), 5)
        self.assertEqual(call_count, 1)
        self.assertEqual(expensive_function(2, 3), 5)
        self.assertEqual(
            call_count, 1
        )  # Should not increase since value already cached
        self.assertEqual(expensive_function(3, 4), 7)
        self.assertEqual(call_count, 2)

    def test_requires_permission(self):
        class User:
            def __init__(self, permissions: list[str]):
                self.permissions = permissions

            def has_permission(self, permission: str) -> bool:
                return permission in self.permissions

        @requires_permission("admin")
        def admin_function(user: User) -> str:
            return "Admin action"

        admin_user = User(["admin", "user"])
        regular_user = User(["user"])

        self.assertEqual(admin_function(admin_user), "Admin action")

        with self.assertRaises(PermissionError):
            admin_function(regular_user)

        with self.assertRaises(AttributeError):
            admin_function("not a user object")


if __name__ == "__main__":
    unittest.main()