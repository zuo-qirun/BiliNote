import importlib.util
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "app" / "utils" / "api_error_diagnosis.py"
    spec = importlib.util.spec_from_file_location("api_error_diagnosis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ApiErrorDiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_auth_error(self):
        result = self.module.diagnose_api_error("登录已过期，请重新登录", 401)
        self.assertEqual(result["code"], "API-AUTH-401")
        self.assertFalse(result["retryable"])

    def test_upload_error(self):
        result = self.module.diagnose_api_error("文件超过服务器允许的最大大小", 413)
        self.assertEqual(result["code"], "API-UPLOAD-413")

    def test_secret_redaction(self):
        result = self.module.diagnose_api_error("api_key=secret-value", 500)
        self.assertNotIn("secret-value", result["technical_message"])


if __name__ == "__main__":
    unittest.main()
