from importlib.metadata import distribution
from pathlib import Path

from omnipanel import __version__


def test_installed_distribution_matches_version() -> None:
    package = distribution("omnipanel")
    assert package.version == __version__
    assert package.metadata["Requires-Python"] == ">=3.12"
    assert any(
        item.name == "omnipanel" and item.value == "omnipanel.cli:main" for item in package.entry_points
    )


def test_typing_marker_is_distributed() -> None:
    import omnipanel

    assert (Path(omnipanel.__file__).parent / "py.typed").is_file()
