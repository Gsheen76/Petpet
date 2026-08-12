from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _release_script():
    return (ROOT / "scripts" / "release.ps1").read_text(encoding="utf-8")


def test_release_script_has_strict_version_and_preflight_gates():
    script = _release_script()
    assert "ValidatePattern" in script
    assert r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$" in script
    assert "version.py" in script
    assert "\\r?$" in script
    assert "RELEASE_NOTES_v$Version.md" in script
    assert "git status --porcelain" in script
    assert "gh auth status" in script
    assert "merge-base --is-ancestor" in script


def test_release_script_checks_local_metadata_before_external_tools():
    script = _release_script()
    assert script.index("$versionSource = Get-Content") < script.index(
        'foreach ($tool in @("python", "git"))'
    )


def test_release_script_can_use_an_ignored_portable_github_cli():
    script = _release_script()
    assert ".tools\\gh" in script
    assert "Get-ChildItem" in script
    assert "$GhCommand" in script


def test_release_script_can_reuse_git_credential_without_persisting_it():
    script = _release_script()
    assert "git credential fill" in script
    assert '$env:GH_TOKEN = $credentialMap["password"]' in script
    assert "gh auth login" in script
    assert "auth login --with-token" not in script
    assert "GH_TOKEN.txt" not in script
    assert '"api", "user", "--jq", ".login"' in script
    assert "$originalGhToken" in script
    assert "Remove-Item Env:GH_TOKEN" in script
    assert script.index('Write-Step "Build Windows with build_windows.ps1"') < script.index(
        'Write-Step "gh auth status"'
    )


def test_release_script_runs_fresh_verification_and_windows_build():
    script = _release_script()
    assert "python -m pytest -q" in script
    assert "python -m py_compile" in script
    assert "git diff --check origin/main...HEAD" in script
    assert "build_windows.ps1" in script
    assert "Petpet.exe" in script
    assert "Compress-Archive" in script
    assert "Get-FileHash" in script


def test_release_script_only_uses_non_destructive_git_operations():
    script = _release_script()
    lowered = script.lower()
    assert "git push --atomic origin head:main refs/tags/$tag" in lowered
    assert "git tag -a" in lowered
    assert "git reset" not in lowered
    assert "git checkout" not in lowered
    assert "--force" not in lowered
    assert "--clobber" not in lowered


def test_release_script_uses_draft_and_four_asset_publication_gate():
    script = _release_script()
    assert "gh release create" in script
    assert "--draft" in script
    assert "gh release upload" in script
    assert "workflow run build-macos.yml" in script
    assert "run watch" in script
    for asset in (
        "Petpet.exe",
        "Petpet-v$Version-windows.zip",
        "Petpet-v$Version-macOS-arm64.zip",
        "Petpet-v$Version-macOS-intel.zip",
    ):
        assert asset in script
    assert "gh release edit" in script
    assert "--draft=false" in script
    assert "--prerelease=false" in script
    assert '.state -ne "uploaded"' in script


def test_release_script_is_resume_safe():
    script = _release_script()
    assert "refs/tags/$Tag^{}" in script
    assert "Existing release tag does not point to HEAD" in script
    assert "already public and complete" in script
    assert "Get-ReleaseAssets" in script
    assert "Missing release assets" in script
    assert "Re-run:" in script
    assert "Compare-RemoteAssetHash" in script
    assert '"release", "download"' in script


def test_release_script_pushes_main_and_tag_atomically():
    script = _release_script()
    verify_index = script.index("Verify existing release tag before mutation")
    create_index = script.index('git tag -a $Tag')
    push_index = script.index('"push", "--atomic", "origin", "HEAD:main", "refs/tags/$Tag"')
    assert verify_index < create_index < push_index
    assert 'git push origin HEAD:main' not in script
    assert 'git tag -d $Tag' in script


def test_release_script_requires_an_annotated_tag():
    script = _release_script()
    assert 'cat-file", "-t", "refs/tags/$Tag"' in script
    assert 'Existing release tag is not annotated' in script


def test_release_script_tracks_the_exact_dispatched_macos_run():
    script = _release_script()
    assert "$dispatchStartedAt" in script
    assert "$dispatchId" in script
    assert '"-f", "dispatch_id=$dispatchId"' in script
    assert 'displayTitle -eq "Build macOS $Tag $dispatchId"' in script
    assert "displayTitle,headSha,createdAt,event" in script
    assert "headSha -eq $headCommit" in script
    assert '"--limit", "100"' in script


def test_release_script_always_prints_the_resume_command_on_failure():
    script = _release_script()
    catch_body = script.split("} catch {", 1)[1]
    assert "Write-Error $_ -ErrorAction Continue" in catch_body
    assert catch_body.index("Write-Error") < catch_body.index("Re-run:")


def test_release_script_stops_the_exact_smoke_process_tree():
    script = _release_script()
    assert "function Stop-ProcessTree" in script
    assert "ParentProcessId" in script
    assert "Stop-ProcessTree $smokeProcess.Id" in script
    smoke_section = script.split('Write-Step "Smoke-test Petpet.exe"', 1)[1].split(
        'Write-Step "Package Windows assets"', 1
    )[0]
    assert "try {" in smoke_section
    assert "finally {" in smoke_section


def test_release_script_performs_post_publication_remote_verification():
    script = _release_script()
    assert "Verify-PublishedRelease" in script
    assert "$asset[0].url" in script
    assert "releases/download/$Tag/" in script
    assert "Final asset" in script
    assert "SHA256" in script
    assert '"final-" + [guid]::NewGuid()' in script


def test_release_script_rechecks_remote_refs_before_dispatch_and_publication():
    script = _release_script()
    assert "function Verify-RemoteRefs" in script
    dispatch_index = script.index('Write-Step "gh workflow run build-macos.yml"')
    publication_index = script.index('Write-Step "gh release edit --draft=false')
    assert script.rfind("Verify-RemoteRefs $headCommit", 0, dispatch_index) >= 0
    assert script.rfind("Verify-RemoteRefs $headCommit", 0, publication_index) > dispatch_index


def test_macos_workflow_skips_an_existing_release_asset():
    workflow = (
        ROOT / ".github" / "workflows" / "build-macos.yml"
    ).read_text(encoding="utf-8")
    assert "gh release view" in workflow
    assert "already exists on the release" in workflow
    assert "gh release upload" in workflow
    assert "--clobber" not in workflow
    assert "ref: ${{ inputs.release_tag || github.ref }}" in workflow
    assert "run-name: Build macOS ${{ inputs.release_tag || github.ref_name }} ${{ inputs.dispatch_id }}" in workflow
    assert "dispatch_id:" in workflow
    assert ".state == \"uploaded\"" in workflow
    assert ".size > 0" in workflow
