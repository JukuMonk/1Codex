"""Integration skeleton; callbacks supplied by project, no database settings."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/workflow'))
from source_guard import FrozenRun, project_lock


def validate_snapshot(project, live, lint):
    # Actual backup/load/compare/export must be implemented by the project.
    with project_lock(project):
        run = FrozenRun(project, live, 'lint')
        try:
            code = run.stage('lint', lambda: lint(run.snapshot))
            run.finish('failed' if code else 'succeeded')
            return code
        finally:
            run.close()
