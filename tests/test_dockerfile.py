from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class DockerfileTests(TestCase):
    def test_dockerfile_builds_swarm_demo_bundle_before_serving(self) -> None:
        instructions = _dockerfile_instructions(ROOT / "Dockerfile")
        run_instruction = 'RUN python3 scripts/build_swarm_demo_bundle.py --out-dir "$SWARM_DEMO_BUNDLE_DIR"'
        cmd_instruction = 'CMD ["python3", "scripts/serve_demo.py", "--host", "0.0.0.0", "--port", "8000"]'
        self.assertIn("ENV SWARM_DEMO_BUNDLE_DIR=/app/runs/demo/swarm", instructions)
        self.assertIn(run_instruction, instructions)
        self.assertIn(cmd_instruction, instructions)
        self.assertLess(instructions.index(run_instruction), instructions.index(cmd_instruction))


def _dockerfile_instructions(path: Path) -> list[str]:
    instructions: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        instructions.append(line)
    return instructions
