from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(TestCase):
    def test_pyproject_defines_zero_dependency_cli_entrypoints(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('requires-python = ">=3.9"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('run-go-gate = "scripts.run_go_gate:main"', text)
        self.assertIn('run-camera-go-gate = "scripts.run_camera_go_gate:main"', text)
        self.assertIn('prepare-sensor-frame-proof-pack = "scripts.prepare_sensor_frame_proof_pack:main"', text)
        self.assertIn('capture-so101-camera-frame = "scripts.capture_so101_camera_frame:main"', text)
        self.assertIn('prepare-so101-operator-probe-pack = "scripts.prepare_so101_operator_probe_pack:main"', text)
        self.assertIn('prepare-qwenguard-physical-go-pack = "scripts.prepare_qwenguard_physical_go_pack:main"', text)
        self.assertIn(
            'audit-qwenguard-submission-readiness = "scripts.audit_qwenguard_submission_readiness:main"',
            text,
        )
        self.assertIn(
            'prepare-qwenguard-final-video-review = "scripts.prepare_qwenguard_final_video_review:main"',
            text,
        )
        self.assertIn('record-qwenguard-trial = "scripts.record_qwenguard_trial:main"', text)
        self.assertIn('prepare-demo-recording-pack = "scripts.prepare_demo_recording_pack:main"', text)
        self.assertIn('prepare-ecs-operator-pack = "scripts.prepare_ecs_operator_pack:main"', text)
        self.assertIn('prepare-dimos-bridge-pack = "scripts.prepare_dimos_bridge_pack:main"', text)
        self.assertIn('collect-dimos-runtime-smoke-report = "scripts.collect_dimos_runtime_smoke_report:main"', text)
        self.assertIn('prepare-dimos-runtime-smoke-pack = "scripts.prepare_dimos_runtime_smoke_pack:main"', text)
        self.assertIn('collect-ecs-smoke-report = "scripts.collect_ecs_smoke_report:main"', text)
        self.assertIn('verify-trace = "scripts.verify_trace:main"', text)

        try:
            import tomllib
        except ModuleNotFoundError:
            return

        parsed = tomllib.loads(text)
        scripts = parsed["project"]["scripts"]
        self.assertEqual(
            scripts["prepare-sensor-frame-proof-pack"],
            "scripts.prepare_sensor_frame_proof_pack:main",
        )
        self.assertEqual(
            scripts["capture-so101-camera-frame"],
            "scripts.capture_so101_camera_frame:main",
        )
        self.assertEqual(
            scripts["prepare-so101-operator-probe-pack"],
            "scripts.prepare_so101_operator_probe_pack:main",
        )
        self.assertEqual(
            scripts["prepare-qwenguard-physical-go-pack"],
            "scripts.prepare_qwenguard_physical_go_pack:main",
        )
        self.assertEqual(
            scripts["audit-qwenguard-submission-readiness"],
            "scripts.audit_qwenguard_submission_readiness:main",
        )
        self.assertEqual(
            scripts["prepare-qwenguard-final-video-review"],
            "scripts.prepare_qwenguard_final_video_review:main",
        )
        self.assertEqual(
            scripts["record-qwenguard-trial"],
            "scripts.record_qwenguard_trial:main",
        )
        self.assertEqual(
            scripts["prepare-demo-recording-pack"],
            "scripts.prepare_demo_recording_pack:main",
        )
        self.assertEqual(
            scripts["prepare-ecs-operator-pack"],
            "scripts.prepare_ecs_operator_pack:main",
        )
        self.assertEqual(
            scripts["prepare-dimos-bridge-pack"],
            "scripts.prepare_dimos_bridge_pack:main",
        )
        self.assertEqual(
            scripts["collect-dimos-runtime-smoke-report"],
            "scripts.collect_dimos_runtime_smoke_report:main",
        )
        self.assertEqual(
            scripts["prepare-dimos-runtime-smoke-pack"],
            "scripts.prepare_dimos_runtime_smoke_pack:main",
        )
