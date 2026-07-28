"""Test that run_job surfaces subprocess failures as job errors."""
from unittest.mock import patch
import api


def test_run_job_failure_sets_error():
    job_id = "test-fail-001"
    request = api.ClipJobRequest(url="https://youtube.com/watch?v=test")
    now = api.now_iso()
    api.jobs[job_id] = api.ClipJob(
        id=job_id,
        status="queued",
        request=request,
        created_at=now,
        updated_at=now,
    )

    with patch("subprocess.Popen", side_effect=OSError("mock error: boom")):
        api.run_job(job_id)

    job = api.jobs[job_id]
    assert job.status == "failed", f"expected failed, got {job.status}"
    assert "boom" in job.error, f"expected 'boom' in error, got: {job.error}"
    api.job_secrets.pop(job_id, None)
    api.jobs.pop(job_id, None)
