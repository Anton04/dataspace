# deps.py — lokal pip-installation till add-onens "modules"
import sys, subprocess, ensurepip
from pathlib import Path

def _pip_cmd():
    # Använd Blenders bundlade Python + se till att pip finns
    try:
        import pip  # noqa: F401
    except Exception:
        ensurepip.bootstrap()
    return [sys.executable, "-m", "pip"]

def ensure_deps(target_dir, requirements):
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    # 1) Försök importera redan installerade
    missing = []
    for req in requirements:
        mod_name = req.split("==")[0].replace("-", "_")
        try:
            __import__(mod_name)
        except Exception:
            missing.append(req)

    if not missing:
        return True, "Alla beroenden finns redan."

    # 2) Installera saknade till add-onens 'modules'
    cmd = _pip_cmd() + [
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--upgrade",
        "--target", str(target),
        *missing
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        return False, f"Pip-fel ({res.returncode}): {err}"

    # 3) Efter installation – se till att Python hittar modulerna nu
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    return True, f"Installerade: {', '.join(missing)}"
