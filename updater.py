"""Cross-platform release checking and staged updates for Petpet."""

from __future__ import annotations

import hashlib
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


RELEASES_URL = "https://api.github.com/repos/Gsheen76/Petpet/releases/latest"
RELEASE_PAGE_URL = "https://github.com/Gsheen76/Petpet/releases/latest"
USER_AGENT = "Petpet-Updater"
LEGACY_UPDATE_DIR_NAMES = {"update", "updates", "updata"}
NETWORK_ATTEMPTS = 2
NETWORK_RETRY_DELAY_SECONDS = 1.0


def _urlopen_with_retries(request, timeout, attempts=NETWORK_ATTEMPTS):
    """Open a URL again after transient connection/TLS failures."""
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt + 1 >= attempts:
                raise
            time.sleep(NETWORK_RETRY_DELAY_SECONDS * (attempt + 1))


def _download_error_message(error):
    """Translate network failures without exposing Python internals to players."""
    if isinstance(error, (urllib.error.URLError, TimeoutError)):
        reason = getattr(error, "reason", error)
        details = str(reason).lower()
        if "timed out" in details or "timeout" in details:
            return "网络连接超时，请稍后重试。"
        return "网络连接失败，请检查网络后重试。"
    return str(error)


def version_tuple(value):
    """Return a comparable numeric tuple for tags such as ``v1.2.3``."""
    numbers = re.findall(r"\d+", str(value).split("-", 1)[0])
    return tuple(int(number) for number in numbers) or (0,)


def is_newer_version(candidate, current):
    return version_tuple(candidate) > version_tuple(current)


def _asset_score(name, platform_name, machine):
    lower = name.lower()
    if lower.endswith((".sha256", ".sha256sum", ".txt")):
        return None

    if platform_name.startswith("win"):
        if any(token in lower for token in ("macos", "darwin", "arm64")):
            return None
        if lower.endswith(".exe"):
            score = 120
        elif lower.endswith(".zip"):
            score = 70
        else:
            return None
        if "windows" in lower or re.search(r"(^|[-_.])win(?:32|64)?($|[-_.])", lower):
            score += 30
        if "setup" in lower or "installer" in lower:
            score += 5
        return score

    if platform_name == "darwin":
        if not lower.endswith((".dmg", ".zip")):
            return None
        if not any(token in lower for token in ("mac", "macos", "darwin")):
            return None
        score = 100 if lower.endswith(".dmg") else 80
        arm_machine = machine.lower() in ("arm64", "aarch64")
        arm_tokens = ("arm64", "aarch64", "apple-silicon", "apple_silicon")
        intel_tokens = ("intel", "x64", "x86_64", "amd64")
        if arm_machine:
            if any(token in lower for token in arm_tokens):
                score += 40
            elif any(token in lower for token in intel_tokens):
                score -= 60
        else:
            if any(token in lower for token in intel_tokens):
                score += 40
            elif any(token in lower for token in arm_tokens):
                score -= 60
        return score

    return None


def select_release_asset(assets, platform_name=None, machine=None):
    """Choose the best release asset for the current OS and CPU."""
    platform_name = platform_name or sys.platform
    machine = machine or platform.machine()
    candidates = []
    for asset in assets or []:
        name = str(asset.get("name") or "")
        url = asset.get("browser_download_url")
        score = _asset_score(name, platform_name, machine)
        if score is not None and url:
            candidates.append((score, name.lower(), asset))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _fetch_release_page_fallback(current_version, platform_name, machine,
                                 timeout):
    """Read the public release page when GitHub's API rate limit is exhausted."""
    request = urllib.request.Request(
        RELEASE_PAGE_URL, headers={"User-Agent": USER_AGENT}
    )
    with _urlopen_with_retries(request, timeout) as response:
        release_page = response.read().decode("utf-8", "ignore")
        release_url = response.geturl()
    match = re.search(r"/releases/tag/([^/?#]+)", release_url)
    if not match:
        return {"status": "error", "message": "无法识别 GitHub 最新版本"}
    raw_tag = urllib.parse.unquote(match.group(1))
    tag = raw_tag.lstrip("vV")
    if not is_newer_version(tag, current_version):
        return {
            "status": "latest",
            "version": tag,
            "release_url": release_url,
        }

    expanded_match = re.search(
        r"https://github\.com/[^\"'<>\s]+/releases/expanded_assets/[^\"'<>\s]+",
        release_page,
    )
    if expanded_match:
        expanded_url = html.unescape(expanded_match.group(0))
    else:
        expanded_url = (
            "https://github.com/Gsheen76/Petpet/releases/expanded_assets/"
            + urllib.parse.quote(raw_tag)
        )
    expanded_request = urllib.request.Request(
        expanded_url, headers={"User-Agent": USER_AGENT}
    )
    with _urlopen_with_retries(expanded_request, timeout) as response:
        expanded_page = response.read().decode("utf-8", "ignore")
    links = sorted(set(re.findall(
        r'href="([^"]*/releases/download/[^"]+)"',
        expanded_page,
    )))
    assets = []
    for link in links:
        url = urllib.parse.urljoin("https://github.com", html.unescape(link))
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
        assets.append({"name": name, "browser_download_url": url})
    asset = select_release_asset(
        assets, platform_name=platform_name, machine=machine
    )
    if not asset:
        return {
            "status": "unsupported",
            "version": tag,
            "release_url": release_url,
            "message": "新版本已发布，但没有找到适用于当前系统的安装包",
        }
    return {
        "status": "update",
        "version": tag,
        "notes": "GitHub API 当前繁忙，更新说明可在发布页面查看。",
        "release_url": release_url,
        "asset_name": asset["name"],
        "download_url": asset["browser_download_url"],
        "asset_size": 0,
        "digest": "",
    }


def fetch_latest_release(current_version, releases_url=RELEASES_URL,
                         platform_name=None, machine=None, timeout=15):
    """Return a structured ``update``, ``latest``, ``unsupported`` or ``error`` result."""
    platform_name = platform_name or sys.platform
    machine = machine or platform.machine()
    try:
        request = urllib.request.Request(releases_url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER_AGENT}/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with _urlopen_with_retries(request, timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            try:
                return _fetch_release_page_fallback(
                    current_version, platform_name, machine, timeout
                )
            except Exception as fallback_exc:
                return {
                    "status": "error",
                    "message": f"GitHub 返回 HTTP {exc.code}；"
                               f"网页回退也失败：{fallback_exc}",
                }
        return {"status": "error", "message": f"GitHub 返回 HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"status": "error", "message": f"网络连接失败：{reason}"}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "error", "message": f"更新信息读取失败：{exc}"}

    tag = str(payload.get("tag_name") or "").lstrip("vV")
    release_url = payload.get("html_url") or releases_url
    if not tag:
        return {"status": "error", "message": "最新版本没有有效的版本号"}
    if not is_newer_version(tag, current_version):
        return {
            "status": "latest",
            "version": tag,
            "release_url": release_url,
        }

    asset = select_release_asset(
        payload.get("assets", []),
        platform_name=platform_name,
        machine=machine,
    )
    if not asset:
        return {
            "status": "unsupported",
            "version": tag,
            "release_url": release_url,
            "message": "新版本已发布，但没有找到适用于当前系统的安装包",
        }
    return {
        "status": "update",
        "version": tag,
        "notes": str(payload.get("body") or "")[:1200],
        "release_url": release_url,
        "asset_name": str(asset.get("name") or "Petpet-update"),
        "download_url": asset.get("browser_download_url"),
        "asset_size": int(asset.get("size") or 0),
        "digest": str(asset.get("digest") or ""),
    }


def check_for_updates_async(current_version, callback, **kwargs):
    """Fetch release information in a daemon thread."""
    def worker():
        callback(fetch_latest_release(current_version, **kwargs))

    thread = threading.Thread(target=worker, daemon=True,
                              name="Petpet-update-check")
    thread.start()
    return thread


def download_release(info, destination_dir, progress=None, cancel_event=None,
                     timeout=60):
    """Download a release asset atomically and validate size/digest when provided."""
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    safe_name = Path(str(info.get("asset_name") or "Petpet-update")).name
    final_path = destination / safe_name
    partial_path = final_path.with_name(final_path.name + ".part")
    expected_size = int(info.get("asset_size") or 0)
    expected_digest = str(info.get("digest") or "")
    if expected_digest.lower().startswith("sha256:"):
        expected_digest = expected_digest.split(":", 1)[1].lower()
    else:
        expected_digest = ""

    try:
        request = urllib.request.Request(info["download_url"], headers={
            "Accept": "application/octet-stream",
            "User-Agent": USER_AGENT,
        })
        digest = hashlib.sha256()
        done = 0
        with _urlopen_with_retries(request, timeout) as response:
            total = int(response.headers.get("Content-Length") or expected_size or 0)
            with open(partial_path, "wb") as output:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError("用户取消了下载")
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        if expected_size and done != expected_size:
            raise OSError(f"文件大小不匹配：{done}/{expected_size}")
        if expected_digest and digest.hexdigest().lower() != expected_digest:
            raise OSError("SHA-256 校验失败")
        os.replace(partial_path, final_path)
        return {"ok": True, "path": str(final_path)}
    except InterruptedError as exc:
        try:
            partial_path.unlink()
        except OSError:
            pass
        return {"ok": False, "cancelled": True, "message": str(exc)}
    except Exception as exc:
        try:
            partial_path.unlink()
        except OSError:
            pass
        return {
            "ok": False,
            "message": _download_error_message(exc),
            "detail": str(exc),
        }


def _extract_windows_executable(download_path, staging_dir):
    path = Path(download_path)
    if path.suffix.lower() == ".exe":
        return path
    if path.suffix.lower() != ".zip":
        raise OSError("Windows 更新包必须是 .exe 或 .zip")
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        candidates = [
            item for item in archive.infolist()
            if not item.is_dir() and Path(item.filename).name.lower() == "petpet.exe"
        ]
        if not candidates:
            raise OSError("ZIP 更新包中没有找到 Petpet.exe")
        candidate = min(candidates, key=lambda item: len(Path(item.filename).parts))
        output_path = staging / "Petpet-update.exe"
        with archive.open(candidate) as source, open(output_path, "wb") as output:
            shutil.copyfileobj(source, output)
        return output_path


def update_cache_dir(version, temp_root=None):
    """Return an ephemeral update cache that cannot become user data."""
    safe_version = re.sub(r"[^0-9A-Za-z._-]+", "-", str(version)).strip("-")
    safe_version = safe_version or "latest"
    root = Path(temp_root or tempfile.gettempdir())
    return root / "Petpet" / "updates" / f"v{safe_version}"


def _legacy_update_cleanup_dir(current_executable):
    """Return the obsolete update directory surrounding a cached executable."""
    current = Path(current_executable).resolve()
    executable_dir = current.parent
    if executable_dir.parent.name.lower() in LEGACY_UPDATE_DIR_NAMES:
        original = executable_dir.parent.parent / current.name
        if original.is_file():
            return executable_dir.parent.resolve()
    elif executable_dir.name.lower() in LEGACY_UPDATE_DIR_NAMES:
        original = executable_dir.parent / current.name
        if original.is_file():
            return executable_dir.resolve()
    return None


def _windows_replacement_target(current_executable):
    """Recover the real install EXE if an old cached update was launched."""
    current = Path(current_executable).resolve()
    executable_dir = current.parent
    if executable_dir.parent.name.lower() in LEGACY_UPDATE_DIR_NAMES:
        original = executable_dir.parent.parent / current.name
        if original.is_file():
            return original.resolve()
    elif executable_dir.name.lower() in LEGACY_UPDATE_DIR_NAMES:
        original = executable_dir.parent / current.name
        if original.is_file():
            return original.resolve()
    return current


def cleanup_stale_windows_updates(current_executable=None, temp_root=None):
    """Remove disposable update payloads without touching user data."""
    current = Path(current_executable or sys.executable).resolve()
    removed = []

    # A failed helper can leave only its hidden, verified pending executable
    # beside Petpet.exe. It is never user data and can be safely discarded on
    # the next launch.
    disposable_patterns = (
        f".{current.stem}.update-*{current.suffix}",
        f".{current.stem}.backup-*{current.suffix}",
    )
    for pattern in disposable_patterns:
        for disposable in current.parent.glob(pattern):
            try:
                disposable.unlink()
                removed.append(str(disposable))
            except OSError:
                pass

    cache_root = (
        Path(temp_root or tempfile.gettempdir()) / "Petpet" / "updates"
    ).resolve()
    try:
        current.relative_to(cache_root)
        current_is_in_cache = True
    except ValueError:
        current_is_in_cache = False

    if cache_root.is_dir() and not current_is_in_cache:
        try:
            shutil.rmtree(cache_root)
            removed.append(str(cache_root))
        except OSError:
            pass
    return removed


def repair_legacy_windows_install(current_executable=None, work_dir=None,
                                  process_id=None):
    """Move a build launched from an old update folder back over the real EXE."""
    current = Path(current_executable or sys.executable).resolve()
    if _windows_replacement_target(current) == current:
        return {"ok": False, "action": "none"}
    work_dir = work_dir or update_cache_dir("repair")
    return launch_windows_replacement(
        current,
        current,
        work_dir,
        process_id=process_id,
    )


def launch_windows_replacement(download_path, current_executable, work_dir,
                               process_id=None):
    """Atomically replace the frozen executable after every bootloader exits."""
    process_id = process_id or os.getpid()
    work_path = Path(work_dir).resolve()
    work_path.mkdir(parents=True, exist_ok=True)
    staged_executable = _extract_windows_executable(download_path, work_path)
    helper_path = work_path.parent / f"apply-update-{int(process_id)}.ps1"
    legacy_cleanup_dir = _legacy_update_cleanup_dir(current_executable)
    target_executable = _windows_replacement_target(current_executable)
    executable_dir = target_executable.parent
    pending_executable = executable_dir / (
        f".{target_executable.stem}.update-{int(process_id)}"
        f"{target_executable.suffix}"
    )
    backup_executable = executable_dir / (
        f".{target_executable.stem}.backup-{int(process_id)}"
        f"{target_executable.suffix}"
    )

    # Prepare the verified replacement next to the target while the app is
    # still alive. This proves the install directory is writable and lets the
    # helper use File.Replace on the same volume once PyInstaller's parent
    # bootloader releases Petpet.exe.
    try:
        shutil.copy2(staged_executable, pending_executable)
        if pending_executable.stat().st_size != staged_executable.stat().st_size:
            raise OSError("更新文件复制不完整")
    except Exception:
        try:
            pending_executable.unlink()
        except OSError:
            pass
        raise

    ps_quote = lambda value: str(value).replace("'", "''")
    cleanup_value = str(legacy_cleanup_dir) if legacy_cleanup_dir else ""
    helper = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$petProcessId = {int(process_id)}\n"
        f"$targetExecutable = '{ps_quote(target_executable)}'\n"
        f"$pendingExecutable = '{ps_quote(pending_executable)}'\n"
        f"$backupExecutable = '{ps_quote(backup_executable)}'\n"
        f"$executableDir = '{ps_quote(executable_dir)}'\n"
        f"$workDir = '{ps_quote(work_path)}'\n"
        f"$legacyCleanupDir = '{ps_quote(cleanup_value)}'\n"
        "Wait-Process -Id $petProcessId -ErrorAction SilentlyContinue\n"
        "$updated = $false\n"
        "$lastUpdateError = ''\n"
        "for ($attempt = 1; $attempt -le 120; $attempt++) {\n"
        "  try {\n"
        "    if (Test-Path -LiteralPath $targetExecutable) {\n"
        "      [System.IO.File]::Replace("
        "$pendingExecutable, $targetExecutable, $backupExecutable, $true)\n"
        "    } else {\n"
        "      [System.IO.File]::Move($pendingExecutable, $targetExecutable)\n"
        "    }\n"
        "    $updated = $true\n"
        "    break\n"
        "  } catch {\n"
        "    $lastUpdateError = $_.Exception.Message\n"
        "    Start-Sleep -Milliseconds 500\n"
        "  }\n"
        "}\n"
        "if ($updated) {\n"
        # Remove the old image before starting the replacement. Starting the
        # new PyInstaller process first can keep the File.Replace backup
        # handle alive and leave a locked .backup-* artifact behind.
        "  for ($attempt = 1; $attempt -le 120; $attempt++) {\n"
        "    try {\n"
        "      if (Test-Path -LiteralPath $backupExecutable) {\n"
        "        Remove-Item -LiteralPath $backupExecutable -Force "
        "-ErrorAction Stop\n"
        "      }\n"
        "      break\n"
        "    } catch {\n"
        "      Start-Sleep -Milliseconds 500\n"
        "    }\n"
        "  }\n"
        "  Start-Process -FilePath $targetExecutable "
        "-WorkingDirectory $executableDir -WindowStyle Hidden\n"
        "} else {\n"
        "  Remove-Item -LiteralPath $pendingExecutable -Force "
        "-ErrorAction SilentlyContinue\n"
        "  Remove-Item -LiteralPath $backupExecutable -Force "
        "-ErrorAction SilentlyContinue\n"
        "  if (Test-Path -LiteralPath $targetExecutable) {\n"
        "    Start-Process -FilePath $targetExecutable "
        "-WorkingDirectory $executableDir -WindowStyle Hidden\n"
        "  }\n"
        "  Add-Type -AssemblyName System.Windows.Forms\n"
        "  [System.Windows.Forms.MessageBox]::Show("
        "\"无法替换原来的 Petpet.exe。`n请确认程序所在文件夹可写后重试。"
        "`n`n$lastUpdateError\", 'Petpet 更新失败', "
        "[System.Windows.Forms.MessageBoxButtons]::OK, "
        "[System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null\n"
        "}\n"
        "Set-Location ([System.IO.Path]::GetTempPath())\n"
        "if ($updated -and $legacyCleanupDir) {\n"
        "  for ($attempt = 1; $attempt -le 40; $attempt++) {\n"
        "    try {\n"
        "      if (Test-Path -LiteralPath $legacyCleanupDir) {\n"
        "        Remove-Item -LiteralPath $legacyCleanupDir -Recurse -Force\n"
        "      }\n"
        "      break\n"
        "    } catch {\n"
        "      Start-Sleep -Milliseconds 500\n"
        "    }\n"
        "  }\n"
        "}\n"
        "Remove-Item -LiteralPath $workDir -Recurse -Force "
        "-ErrorAction SilentlyContinue\n"
        "Remove-Item -LiteralPath $PSCommandPath -Force "
        "-ErrorAction SilentlyContinue\n"
    )
    helper_path.write_text(helper, encoding="utf-8-sig", newline="\r\n")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", str(helper_path),
            ],
            cwd=str(work_path.parent),
            creationflags=creation_flags,
            close_fds=True,
        )
    except Exception:
        try:
            pending_executable.unlink()
        except OSError:
            pass
        try:
            helper_path.unlink()
        except OSError:
            pass
        raise
    return {"ok": True, "action": "restart"}


def open_macos_update(download_path):
    """Open the downloaded macOS package with Finder/Archive Utility."""
    subprocess.Popen(["open", str(Path(download_path).resolve())], close_fds=True)
    return {"ok": True, "action": "open"}
