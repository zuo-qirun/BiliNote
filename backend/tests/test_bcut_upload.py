"""必剪上传状态隔离与提交重试的回归测试。"""

import importlib.util
import json
import logging
import pathlib
import sys
import types
import unittest


def _install_stubs():
    app_mod = types.ModuleType("app")
    transcriber_pkg = types.ModuleType("app.transcriber")
    models_pkg = types.ModuleType("app.models")

    decorators_mod = types.ModuleType("app.decorators.timeit")
    decorators_mod.timeit = lambda function: function

    transcriber_model_mod = types.ModuleType("app.models.transcriber_model")

    class _TranscriptSegment:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _TranscriptResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    transcriber_model_mod.TranscriptSegment = _TranscriptSegment
    transcriber_model_mod.TranscriptResult = _TranscriptResult

    base_mod = types.ModuleType("app.transcriber.base")

    class _Transcriber:
        pass

    base_mod.Transcriber = _Transcriber

    logger_mod = types.ModuleType("app.utils.logger")
    logger_mod.get_logger = logging.getLogger

    events_mod = types.ModuleType("events")

    class _Signal:
        def send(self, _payload):
            return None

    events_mod.transcription_finished = _Signal()

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.transcriber", transcriber_pkg)
    sys.modules.setdefault("app.models", models_pkg)
    sys.modules["app.decorators.timeit"] = decorators_mod
    sys.modules["app.models.transcriber_model"] = transcriber_model_mod
    sys.modules["app.transcriber.base"] = base_mod
    sys.modules["app.utils.logger"] = logger_mod
    sys.modules["events"] = events_mod


def _load_bcut_module():
    _install_stubs()
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "transcriber" / "bcut.py"
    spec = importlib.util.spec_from_file_location("bcut_upload_test", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("bcut module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bcut = _load_bcut_module()


class _FakeResponse:
    def __init__(self, payload=None, headers=None):
        self._payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, etags, commit_responses):
        self.etags = list(etags)
        self.commit_responses = list(commit_responses)
        self.commit_payloads = []

    def post(self, url, data=None, **_kwargs):
        if url == bcut.API_REQ_UPLOAD:
            size = len(b"test audio payload")
            return _FakeResponse({
                "data": {
                    "in_boss_key": "boss-key",
                    "resource_id": "resource-id",
                    "upload_id": "upload-id",
                    "upload_urls": [
                        f"https://upload.invalid/{index}"
                        for index in range(len(self.etags))
                    ],
                    "per_size": 10,
                    "size": size,
                }
            })
        if url == bcut.API_COMMIT_UPLOAD:
            self.commit_payloads.append(json.loads(data))
            return _FakeResponse(self.commit_responses.pop(0))
        raise AssertionError(f"unexpected POST URL: {url}")

    def put(self, _url, **_kwargs):
        etag = self.etags.pop(0)
        return _FakeResponse(headers={"Etag": f'"{etag}"'})


class TestBcutUpload(unittest.TestCase):
    def setUp(self):
        self.transcriber = bcut.BcutTranscriber()
        self.transcriber.commit_retry_base_seconds = 0
        self.audio_path = pathlib.Path(__file__).with_name("_bcut_test_audio.mp3")
        self.audio_path.write_bytes(b"test audio payload")

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    def test_commit_retries_retryable_service_error(self):
        self.transcriber.commit_max_attempts = 3
        session = _FakeSession(
            etags=["etag-a", "etag-b"],
            commit_responses=[
                {"code": 139201, "message": "第三方服务异常"},
                {
                    "code": 0,
                    "data": {"download_url": "https://download.invalid/audio"},
                },
            ],
        )

        download_url = self.transcriber._upload(
            str(self.audio_path),
            session,
        )

        self.assertEqual(download_url, "https://download.invalid/audio")
        self.assertEqual(len(session.commit_payloads), 2)
        self.assertEqual(session.commit_payloads[0]["Etags"], "etag-a,etag-b")

    def test_upload_state_does_not_leak_between_tasks(self):
        self.transcriber.commit_max_attempts = 1
        first = _FakeSession(
            etags=["first"],
            commit_responses=[
                {"code": 0, "data": {"download_url": "https://one.invalid"}},
            ],
        )
        second = _FakeSession(
            etags=["second-a", "second-b"],
            commit_responses=[
                {"code": 0, "data": {"download_url": "https://two.invalid"}},
            ],
        )

        self.transcriber._upload(str(self.audio_path), first)
        self.transcriber._upload(str(self.audio_path), second)

        self.assertEqual(first.commit_payloads[0]["Etags"], "first")
        self.assertEqual(
            second.commit_payloads[0]["Etags"],
            "second-a,second-b",
        )


if __name__ == "__main__":
    unittest.main()
