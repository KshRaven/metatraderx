"""Project-specific settings for pypimgr in this repository."""

PROJECT_NAME = "metatraderx"
PYPI_PACKAGE_NAME = "metatraderx"
GIT_REMOTE = "origin"
TAG_PREFIX = "v"
RELEASE_COMMIT_TEMPLATE = "Release v{version}"

PROJECT_FILE = "pyproject.toml"
CHANGELOG_FILE = "CHANGELOG.md"
ENV_FILE = ".env.release"
COMMIT_MESSAGE_FILE = "commit.txt"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    PROJECT_FILE,
    CHANGELOG_FILE,
    "MANIFEST.in",
    ".gitignore",
)
TOP_LEVEL_EXCLUDES = ("data",)
EXTRA_FORBIDDEN_PATHS = (r"(^|/)experimental/", r"(^|/)data/")

# No desktop or mobile apps; every tagged release creates a GitHub release with the sdist and wheel and publishes
# to TestPyPI and PyPI.
APP_PATHS = ()
VERSION_TARGETS = ()

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"

PROJECT_LINKS = {
    "Repository": "https://github.com/KshRaven/metatraderx",
    "Release workflow": "https://github.com/KshRaven/metatraderx/actions/workflows/release.yml",
    "Docs": "https://kshraven.github.io/metatraderx/",
    "PyPI": "https://pypi.org/project/metatraderx/",
    "TestPyPI": "https://test.pypi.org/project/metatraderx/",
    "PyPI publisher settings": "https://pypi.org/manage/project/metatraderx/settings/publishing/",
    "TestPyPI publisher settings": "https://test.pypi.org/manage/project/metatraderx/settings/publishing/",
}
