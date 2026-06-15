from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class DockerfileTests(TestCase):
    def test_dockerfile_builds_swarm_demo_bundle_before_serving(self) -> None:
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("RUN python3 scripts/build_swarm_demo_bundle.py", text)
        self.assertIn('CMD ["python3", "scripts/serve_demo.py", "--host", "0.0.0.0", "--port", "8000"]', text)
