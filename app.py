#!/usr/bin/env python3
# thoth-storages
# Copyright(C) 2021 Fridolin Pokorny
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Automatically construct prescriptions linking GitHub release notes for GitHub hosted projects."""

import logging
import sys
from datetime import date
from datetime import datetime
from typing import Any
from typing import Dict
from typing import Optional
from urllib.parse import urlparse

import click
import requests
import yaml
from packaging.utils import canonicalize_name
from thoth.common import init_logging
from thoth.storages import SolverResultsStore

init_logging()
_LOGGER = logging.getLogger("thoth.prescriptions.gh_release_notes")
_DATE_FORMAT = "%Y-%m-%d"

__version__ = "0.0.0"
__component_version__ = f"{__version__}"


def _get_release_notes_entry(
    org: str, repo: str, metadata: Dict[str, str], has_v_prefix: bool = False
) -> Dict[str, Any]:
    """Get an entry to the prescription release notes."""
    result = {
        "organization": org,
        "repository": repo,
        "package_version": {
            "name": canonicalize_name(metadata["Name"]),
            "version": f"==={metadata['Version']}",
            "index_url": "https://pypi.org/simple",
        },
    }

    if has_v_prefix:
        result["tag_version_prefix"] = "v"

    return result


def construct_prescription_gh_release_notes(*, start_date: Optional[date], end_date: Optional[date]) -> Dict[str, Any]:
    """Construct prescriptions for GitHub release notes."""
    solver_results = SolverResultsStore()
    solver_results.connect()

    release_notes = []
    release_notes_seen = set()
    for document_id, doc in solver_results.iterate_results(
        start_date=start_date, end_date=end_date, include_end_date=True
    ):
        if not doc["result"]["tree"]:
            continue

        _LOGGER.debug("Processing solver document %r", document_id)

        # We pick only the first entry, this is OK for deployment as solver is run just once per package.
        metadata = doc["result"]["tree"][0]["importlib_metadata"]["metadata"]

        # Check metadata available.
        version = metadata.get("Version")
        if not version:
            continue

        name = metadata.get("Name")
        if not name:
            continue

        # Do not construct duplicate entries.
        if (name, version) in release_notes_seen:
            continue

        release_notes_seen.add((name, version))

        url_candidates = [metadata.get("Home-page")]
        for url in metadata.get("Project-URL") or []:
            url_candidates.append(url.rsplit(",", maxsplit=1)[-1].strip())

        for url in url_candidates:
            if not url or not url.startswith("https://github.com"):
                _LOGGER.debug(
                    "Skipping URL %r as no link to GitHub repository found",
                    url,
                )
                continue

            url_path_parts = urlparse(url).path.split("/")[1:]
            if len(url_path_parts) < 2:
                _LOGGER.warning(
                    "Skipping URL as GitHub repository and organization cannot be parsed",
                    url,
                )
                continue

            org, repo = url_path_parts[:2]

            # Try without `v' prefix.
            release_url = f"https://github.com/{org}/{repo}/releases/tag/{metadata.get('Version')}"
            response = requests.head(release_url, allow_redirects=True)
            if response.status_code == 200:
                entry = _get_release_notes_entry(org, repo, metadata, has_v_prefix=False)
                _LOGGER.info("Found GitHub release notes at %s", release_url)
                release_notes.append(entry)
                break

            # Try with `v' prefix.
            release_url = f"https://github.com/{org}/{repo}/releases/tag/v{metadata.get('Version')}"
            response = requests.head(release_url, allow_redirects=True)
            if response.status_code == 200:
                entry = _get_release_notes_entry(org, repo, metadata, has_v_prefix=True)
                _LOGGER.info("Found GitHub release notes at %s", release_url)
                break

    return {
        "name": "PyPIGitHubReleaseNotesWrap",
        "type": "wrap.GitHubReleaseNotes",
        "should_include": {
            "adviser_pipeline": True,
        },
        "run": {
            "release_notes": release_notes,
        },
    }


def _print_version(ctx: click.Context, _, value: str):
    """Print adviser version and exit."""
    if not value or ctx.resilient_parsing:
        return

    click.echo(__version__)
    ctx.exit()


@click.command()
@click.pass_context
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    envvar="THOTH_PRESCRIPTIONS_GH_RELEASE_NOTES_DEBUG",
    help="Be verbose about what's going on.",
)
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    callback=_print_version,
    expose_value=False,
    help="Print version and exit.",
)
@click.option(
    "--start-date",
    envvar="THOHT_PRESCRIPTIONS_GH_RELEASE_NOTES_START_DATE",
    help="Use solver results starting the given date.",
    metavar="YYYY-MM-DD",
    type=str,
)
@click.option(
    "--end-date",
    help="Upper bound for solver results listing.",
    metavar="YYYY-MM-DD",
    envvar="THOHT_PRESCRIPTIONS_GH_RELEASE_NOTES_END_DATE",
    type=str,
)
@click.option(
    "--output",
    help="Store result to a file or print to stdout (-).",
    metavar="FILE",
    envvar="THOHT_PRESCRIPTIONS_GH_RELEASE_NOTES_OUTPUT",
    type=str,
)
def cli(
    _: click.Context,
    verbose: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output: Optional[str] = None,
):
    """Aggregate GitHub release notes prescriptions for GitHub hosted projects on PyPI."""
    if verbose:
        _LOGGER.setLevel(logging.DEBUG)

    _LOGGER.debug("Debug mode is on")
    _LOGGER.info("Version: %s", __component_version__)

    start_date_converted = None
    if start_date:
        start_date_converted = datetime.strptime(start_date, _DATE_FORMAT).date()

    end_date_converted = None
    if end_date:
        end_date_converted = datetime.strptime(end_date, _DATE_FORMAT).date()

    prescriptions = construct_prescription_gh_release_notes(
        start_date=start_date_converted, end_date=end_date_converted
    )

    if output == "-" or not output:
        yaml.safe_dump(prescriptions, sys.stdout)
    else:
        with open(output, "w") as f:
            yaml.safe_dump(prescriptions, f)


__name__ == "__main__" and cli()
