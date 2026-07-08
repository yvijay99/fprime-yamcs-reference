"""
Pytest configuration for FprimeYamcsReference integration tests.

Copies test files from the fprime submodule to /tmp/ before running tests.
Integration tests (FileManager, FileDownlink, CmdSequencer) expect test files
like test_seq.seq and 1MiB.txt to exist at /tmp/ on the target filesystem.
"""

import shutil
import pytest
import subprocess
from pathlib import Path


def find_fprime_location():
    """
    Find the fprime submodule location.

    Tries local dev (lib/fprime), CI artifacts (fprime-svc/), git submodule path,
    and FPRIME_LOCATION environment variable.
    """
    current_file = Path(__file__).resolve()
    potential_submodule = current_file.parent.parent.parent.parent.parent / "lib" / "fprime"
    if potential_submodule.exists() and (potential_submodule / "Svc").exists():
        return potential_submodule

    # CI artifacts: fprime Svc directory is copied to fprime-svc/
    cwd = Path.cwd()
    fprime_svc = cwd / "fprime-svc"
    if fprime_svc.exists() and fprime_svc.is_dir():
        return fprime_svc

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=current_file.parent,
            check=True
        )
        repo_root = Path(result.stdout.strip())
        fprime_path = repo_root / "lib" / "fprime"
        if fprime_path.exists() and (fprime_path / "Svc").exists():
            return fprime_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    import os
    if "FPRIME_LOCATION" in os.environ:
        fprime_path = Path(os.environ["FPRIME_LOCATION"])
        if fprime_path.exists() and (fprime_path / "Svc").exists():
            return fprime_path

    return None


@pytest.fixture(scope="session", autouse=True)
def setup_test_files():
    """
    Copy test files from fprime submodule to /tmp/ before tests run.

    Integration tests expect test_seq.seq, test_seq_wait.seq, and 1MiB.txt
    to exist at /tmp/ on the target filesystem.
    """
    fprime_lib = find_fprime_location()

    if fprime_lib is None:
        print("Warning: Could not locate fprime repository. Test files will not be copied.")
        yield
        return

    print(f"Found fprime location: {fprime_lib}")

    if (fprime_lib / "FileUplink").exists():
        source_dir = fprime_lib / "FileUplink" / "test" / "int"
    else:
        source_dir = fprime_lib / "Svc" / "FileUplink" / "test" / "int"

    test_files = ["test_seq.seq", "test_seq_wait.seq", "1MiB.txt"]

    for filename in test_files:
        source = source_dir / filename
        dest = Path("/tmp") / filename

        if source.exists():
            try:
                shutil.copy2(source, dest)
                print(f"Copied {source} -> {dest}")
            except (IOError, PermissionError) as e:
                print(f"Warning: Could not copy {filename} to /tmp/: {e}")
        else:
            print(f"Warning: Source file {source} does not exist")

    yield
