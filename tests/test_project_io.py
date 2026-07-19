from pathlib import Path
from wall_survey.model import Location, Reference, Run, SurveyProject
from wall_survey.project_io import load_project, save_project


def test_portable_project_round_trip(tmp_path):
    source = Path(__file__).parents[1] / "example_s2p_files" / "example_baseline.s2p"
    project = SurveyProject(name="Test", references=[Reference(name="Air", runs=[Run(source=str(source))])], locations=[Location(label="A1", x_m=.1, y_m=.2, runs=[Run(source=str(source))])], loose_runs=[Run(label="Known wall", source=str(source))])
    path = save_project(project, tmp_path / "test.wallscan")
    restored = load_project(path, tmp_path / "extracted")
    assert restored.name == "Test"
    assert restored.locations[0].x_m == .1
    assert Path(restored.locations[0].runs[0].source).exists()
    assert restored.loose_runs[0].label == "Known wall"
