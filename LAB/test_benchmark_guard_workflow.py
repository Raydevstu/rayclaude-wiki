from benchmark_guard_workflow import benchmark
from test_guard_orchestrator import workflow
from scope_guard import ChangedFile


def test_integrated_benchmark_reports_success_and_blocking_without_false_success():
    report = benchmark((workflow(), workflow(changed_files=(ChangedFile("ROADMAP.md", 1, "utility"),))))
    assert report["cases"] == 2
    assert report["verified"] == 1
    assert report["blocked"] == 1
    assert report["false_success_rate"] == 0.0
    assert report["scope_violations"] == 1
