"""发布元数据门禁：pyproject 版本与运行时 ``__version__`` 必须一致。

damai 的版本号有两个载体（`pyproject.toml` 的 `[project].version` 与
`automation_app_damai.__version__`）。0.3.1 bump 时只改了前者，两者漂移而测试
不红——安装元数据声明 0.3.1、运行时自报 0.3.0。这里把一致性做成测试。
"""

from __future__ import annotations

import re
from pathlib import Path

import automation_app_damai

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_version_matches_runtime_version():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = pyproject.split("[project]", 1)
    assert len(project_section) == 2, "pyproject.toml 缺少 [project] 段"
    match = re.search(
        r'^\s*version\s*=\s*"([^"]+)"', project_section[1], re.MULTILINE
    )
    assert match is not None, "[project] 段缺少 version"
    assert match.group(1) == automation_app_damai.__version__, (
        "pyproject version 与 __version__ 漂移："
        f"{match.group(1)!r} != {automation_app_damai.__version__!r}"
    )
