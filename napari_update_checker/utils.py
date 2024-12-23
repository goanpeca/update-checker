import json
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import packaging
import packaging.version
from napari.utils.misc import running_as_constructor_app
from napari.utils.notifications import show_warning

ON_BUNDLE = running_as_constructor_app()


@lru_cache
def github_tags(url: str = 'https://api.github.com/repos/napari/napari/tags'):
    with urlopen(url) as r:
        data = json.load(r)

    versions = []
    for item in data:
        version = item.get('name', None)
        if version:
            if version.startswith('v'):
                version = version[1:]

            versions.append(version)
    return list(reversed(versions))


@lru_cache
def conda_forge_releases(
    url: str = 'https://api.anaconda.org/package/conda-forge/napari/',
):
    with urlopen(url) as r:
        data = json.load(r)
    versions = data.get('versions', [])
    return versions


def get_latest_version(github: Optional[bool] = None):
    """Check latest version between tags and conda forge depending on type of napari install."""
    if github is None:
        versions_func = conda_forge_releases if ON_BUNDLE else github_tags
    else:
        versions_func = github_tags if github is True else conda_forge_releases

    versions = []
    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(versions_func)

        versions = future.result()
    except (HTTPError, URLError):
        show_warning(
            'Update checker: There seems to be an issue with network connectivity. '
        )
        return None

    if versions:
        return packaging.version.parse(versions[-1])
    return None


def is_conda_environment(path):
    return (Path(path) / 'conda-meta').exists()


def is_version_installed(version, pkg_name='napari'):
    envs_folder = Path(sys.prefix)
    env = envs_folder.parent / f'{pkg_name}-{version}'
    return env.exists() and is_conda_environment(env)
