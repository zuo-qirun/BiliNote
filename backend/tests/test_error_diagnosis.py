import unittest

from app.utils.error_diagnosis import diagnose_task_error


class ErrorDiagnosisTests(unittest.TestCase):
    def test_blocked_request_is_actionable(self):
        result = diagnose_task_error("Your request was blocked.", stage="unknown")

        self.assertEqual(result["code"], "AI_PROVIDER_BLOCKED")
        self.assertEqual(result["stage"], "summarizing")
        self.assertFalse(result["retryable"])
        self.assertGreaterEqual(len(result["possible_causes"]), 3)

    def test_credentials_are_redacted(self):
        result = diagnose_task_error("api_key=super-secret token: abc123")

        self.assertNotIn("super-secret", result["technical_message"])
        self.assertNotIn("abc123", result["technical_message"])

    def test_stage_hint_is_preserved_for_generic_error(self):
        result = diagnose_task_error("unexpected response", stage="transcribing")

        self.assertEqual(result["stage"], "transcribing")


if __name__ == "__main__":
    unittest.main()
