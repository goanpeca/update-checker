import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError

from napari_update_checker.utils import (
    conda_forge_releases,
    get_latest_version,
    github_tags,
    is_conda_environment,
    is_version_installed,
)


def test_github_tags():
    try:
        data = github_tags()
        assert data[0] == '0.5.0a1'  # Oldest version available
        assert len(data) >= 30
    except (HTTPError, URLError):
        pass


def test_conda_forge_releases():
    try:
        data = conda_forge_releases()
        assert data[0] == '0.2.12'  # Oldest version available
        assert len(data) >= 35
    except (HTTPError, URLError):
        pass


def test_get_latest_version(monkeypatch):
    result = get_latest_version(github=None)
    assert result
    result = get_latest_version(github=True)
    assert result
    result = get_latest_version(github=False)
    assert result


def test_is_conda_environment():
    conda_envs = tempfile.mkdtemp(prefix='envs')
    env = Path(conda_envs) / 'env-name'
    meta = env / 'conda-meta'
    meta.mkdir(parents=True)
    assert is_conda_environment(env)
    assert not is_conda_environment(meta)


def test_is_version_installed(monkeypatch):
    conda_envs = tempfile.mkdtemp(prefix='envs')
    env = Path(conda_envs) / 'boom-1.0.0'
    monkeypatch.setattr(sys, 'prefix', env)
    meta = env / 'conda-meta'
    meta.mkdir(parents=True)
    assert is_version_installed('1.0.0', pkg_name='boom')
    assert not is_version_installed('2.0.0')
