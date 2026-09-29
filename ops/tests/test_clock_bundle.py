"""Clock preparation must not turn an archive or manifest into an arbitrary privileged write."""

import hashlib
import importlib.util
import io
import json
import os
import stat
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "provision_clock.py"
VENDOR_PREIMAGE = b"                    os.link(tarinfo._link_target, targetpath)"
VENDOR_POSTIMAGE = b"\n".join([
    b"                    # Resolve the target so the hard link points to the file",
    b"                    # itself. Otherwise os.link() may duplicate a symlink to a",
    b"                    # shallower location, where it's relative target escapes the",
    b"                    # destination directory. (CVE-2026-82049)",
    b"                    os.link(os.path.realpath(tarinfo._link_target), targetpath)",
])


@pytest.fixture
def clock_tools():
    spec = importlib.util.spec_from_file_location("clock_provision", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as stream:
        for name, content, link in entries:
            item = tarfile.TarInfo(name)
            if link is not None:
                item.type, item.linkname = tarfile.SYMTYPE, link
                stream.addfile(item)
            else:
                item.size = len(content)
                stream.addfile(item, io.BytesIO(content))
    return output.getvalue()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape", "a\\b", "a\nb"])
def test_manifest_paths_cannot_escape_the_install_root(clock_tools, name):
    with pytest.raises(ValueError):
        clock_tools.relative_name(name)


def test_archive_rejects_traversal_before_writing(clock_tools, tmp_path):
    raw = archive([("source/good", b"good", None), ("../escape", b"bad", None)])
    with pytest.raises(ValueError):
        clock_tools.extract_archive(raw, tmp_path / "extract", "source")
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "extract").exists()


def test_archive_cannot_link_to_an_external_file(clock_tools, tmp_path):
    raw = archive([("source/bin/tool", b"", "/etc/passwd")])
    with pytest.raises(ValueError):
        clock_tools.extract_archive(raw, tmp_path / "extract", "source")
    assert not (tmp_path / "extract").exists()


def test_verified_internal_alias_becomes_a_regular_frozen_file(clock_tools, tmp_path):
    raw = archive([("source/bin/python3.13", b"binary", None),
                   ("source/bin/python3", b"", "python3.13")])
    source = clock_tools.extract_archive(raw, tmp_path / "extract", "source")
    clock_tools.freeze_tree(source, tmp_path / "frozen")
    alias = tmp_path / "frozen/bin/python3"
    assert not alias.is_symlink() and alias.read_bytes() == b"binary"


def test_download_digest_mismatch_never_extracts_code(clock_tools, tmp_path, monkeypatch):
    raw = archive([("source/tool", b"untrusted", None)])
    monkeypatch.setattr(clock_tools.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(raw))
    with pytest.raises(ValueError, match="digest"):
        clock_tools.download("https://example.invalid/source", "0" * 64, tmp_path / "archive")
    assert not (tmp_path / "archive").exists()


def test_download_cache_is_reverified(clock_tools, tmp_path):
    value = tmp_path / "archive"
    value.write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        clock_tools.download(
            "https://example.invalid/source", hashlib.sha256(b"original").hexdigest(), value,
        )


@pytest.fixture
def bundle(clock_tools, tmp_path, monkeypatch):
    root = tmp_path / "work"
    payload = root / "bundle"
    for name in ("runtime/bin/python3.13", "native/chronyd", "native/chronyc"):
        path = payload / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture-only:" + name.encode())
        path.chmod(0o755)
    ca = tmp_path / "ca.pem"
    ca.write_bytes(b"fixture-public-ca")
    monkeypatch.setattr(clock_tools, "SYSTEM_CA", ca)
    monkeypatch.setattr(clock_tools.pwd, "getpwnam",
                        lambda name: SimpleNamespace(pw_uid=608,pw_gid=608))
    # Manifest/installation fixtures use small payload pins, never a network download.
    module = payload / clock_tools.TARFILE_PATH
    module.parent.mkdir(parents=True)
    module.write_bytes(b"fixture-only:patched-runtime")
    monkeypatch.setattr(clock_tools, "TARFILE_AFTER_SHA",
                        clock_tools.fingerprint(module.read_bytes()))
    monkeypatch.setattr(clock_tools, "apply_tarfile_backport",
                        lambda work: clock_tools.runtime_patch())
    result = clock_tools.seal_bundle(root, "r1t-clock-fixture")
    return root, result["manifestSha256"]


def rewrite_manifest(clock_tools, work):
    path = work / "bundle.json"
    value = json.loads(path.read_bytes())
    value["files"] = clock_tools.inventory(work / "bundle")
    data = clock_tools.json_bytes(value)
    path.write_bytes(data)
    return clock_tools.fingerprint(data)


def test_plan_only_verifies_the_bundle_without_privileged_writes(clock_tools, bundle, monkeypatch):
    work, expected = bundle
    monkeypatch.setattr(clock_tools, "ensure_directory", lambda *a, **kw: pytest.fail("plan wrote"))
    assert clock_tools.install(work, expected)["state"] == "PLAN_ONLY"


def test_actual_install_requires_operator_authentication(clock_tools, bundle, monkeypatch):
    monkeypatch.setattr(clock_tools.os, "getuid", lambda: 501)
    monkeypatch.setattr(clock_tools.os, "geteuid", lambda: 501)
    with pytest.raises(PermissionError, match="authenticate"):
        clock_tools.install(*bundle, apply=True)


def test_install_uses_verified_system_ca_bytes_despite_staging_swap(
    clock_tools, bundle, tmp_path, monkeypatch,
):
    work, expected = bundle
    manifest = clock_tools.verify_bundle(work, expected)
    original_read = clock_tools.read_regular
    ca_bytes = b"fixture-public-ca"
    staged_ca = work / "bundle/config/nts-ca.pem"
    system_ca = SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=0))

    def read_with_staging_swap(path, *args, **kwargs):
        if path is system_ca:
            staged_ca.write_bytes(b"unreviewed-ca")
            return ca_bytes
        return original_read(path, *args, **kwargs)

    copied = []

    def capture_install(path, data, **kwargs):
        if path.name == "ca-" + manifest["systemCaSha256"] + ".pem":
            copied.append(data)
            staged_ca.write_bytes(ca_bytes)  # Restore before the later artifact-copy loop.

    monkeypatch.setattr(clock_tools, "ROOT", tmp_path / "installed")
    monkeypatch.setattr(clock_tools, "verify_bundle", lambda *args: manifest)
    monkeypatch.setattr(clock_tools, "require_protected_operator", lambda: None)
    monkeypatch.setattr(clock_tools, "SYSTEM_CA",
                        SimpleNamespace(resolve=lambda **kwargs: system_ca))
    monkeypatch.setattr(clock_tools, "read_regular", read_with_staging_swap)
    monkeypatch.setattr(clock_tools, "ensure_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(clock_tools, "install_file", capture_install)
    monkeypatch.setattr(clock_tools.shutil, "disk_usage", lambda path: SimpleNamespace(free=2**40))
    monkeypatch.setattr(clock_tools, "run", lambda *args, **kwargs: '{"state":"INSTALLED"}')
    assert clock_tools.install(work, expected, apply=True)["state"] == "INSTALLED_NOT_ACCEPTED"
    assert copied == [ca_bytes]


def test_tampered_or_unregistered_files_cannot_be_installed(clock_tools, bundle):
    work, expected = bundle
    binary = work / "bundle/native/chronyd"
    binary.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest"):
        clock_tools.verify_bundle(work, expected)
    binary.write_bytes(b"fixture-only:native/chronyd")
    (work / "bundle/runtime/extra.py").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="unregistered"):
        clock_tools.verify_bundle(work, expected)


def test_reviewed_manifest_cannot_widen_the_two_clock_jobs(clock_tools, bundle):
    work, _ = bundle
    path = work / "bundle/config/deployment.json"
    value = json.loads(path.read_bytes())
    value["entries"][0]["argv"][1] = "-q"  # Would adjust the system clock.
    path.write_bytes(clock_tools.json_bytes(value))
    expected = rewrite_manifest(clock_tools, work)
    with pytest.raises(ValueError, match="two fixed clock jobs"):
        clock_tools.verify_bundle(work, expected)


def test_observer_cannot_disable_nts_or_add_an_untrusted_source(clock_tools, bundle):
    work, _ = bundle
    path = work / "bundle/config/chrony.conf"
    path.write_bytes(path.read_bytes() + b"server untrusted.example\nnocerttimecheck 1\n")
    expected = rewrite_manifest(clock_tools, work)
    with pytest.raises(ValueError, match="fixed policy"):
        clock_tools.verify_bundle(work, expected)


@pytest.mark.parametrize("record", [None, {}, {"cve": "CVE-2026-82049"}])
def test_install_rejects_an_unverified_patch_claim(clock_tools, bundle, record):
    work, _ = bundle
    path = work / "bundle.json"
    manifest = json.loads(path.read_bytes())
    manifest["runtimePatch"] = record
    data = clock_tools.json_bytes(manifest)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="runtime patch"):
        clock_tools.install(work, clock_tools.fingerprint(data))


def test_reviewed_metadata_cannot_vouch_for_an_unpatched_module(clock_tools, bundle):
    work, _ = bundle
    module = work / "bundle" / clock_tools.TARFILE_PATH
    module.write_bytes(b"unpatched-runtime")
    expected = rewrite_manifest(clock_tools, work)  # Even a new outer digest is insufficient.
    with pytest.raises(ValueError, match="postimage"):
        clock_tools.install(work, expected)
    assert module.read_bytes() == b"unpatched-runtime"


@pytest.mark.parametrize("name", ["tarfile.pyc", "__pycache__/tarfile.cpython-313.pyc"])
def test_reviewed_bundle_cannot_load_cached_unpatched_tarfile(clock_tools, bundle, name):
    work, _ = bundle
    module = work / "bundle" / clock_tools.TARFILE_PATH
    shadow = module.parent / name
    shadow.parent.mkdir(exist_ok=True)
    shadow.write_bytes(b"unpatched-bytecode")
    expected = rewrite_manifest(clock_tools, work)
    with pytest.raises(ValueError, match="unverified bytecode"):
        clock_tools.install(work, expected)
    assert shadow.read_bytes() == b"unpatched-bytecode"


def test_backport_verification_binds_manifest_without_repair(clock_tools, bundle, monkeypatch):
    work, expected = bundle
    before = clock_tools.inventory(work / "bundle")
    monkeypatch.setattr(clock_tools, "apply_tarfile_backport",
                        lambda *_: pytest.fail("verification repaired the candidate"))
    result = {"state": "VENDOR_BACKPORT_VERIFIED", "cve": "CVE-2026-82049",
              "filters": ["data", "tar"]}
    monkeypatch.setattr(clock_tools, "run", lambda *a, **k: json.dumps(result))
    proof = clock_tools.verify_tarfile_backport(work, expected)
    assert proof["manifestSha256"] == expected
    assert proof["patch"] == clock_tools.runtime_patch()
    assert proof["accepted"] is False
    assert clock_tools.inventory(work / "bundle") == before
    assert json.loads((work / "tarfile-remediation.json").read_bytes()) == proof


def test_backport_verification_refuses_to_repair_a_broken_candidate(
    clock_tools, bundle, monkeypatch,
):
    work, expected = bundle
    module = work / "bundle" / clock_tools.TARFILE_PATH
    module.write_bytes(b"unpatched-runtime")
    monkeypatch.setattr(clock_tools, "run", lambda *a, **k: pytest.fail("ran broken candidate"))
    with pytest.raises(ValueError, match="digest"):
        clock_tools.verify_tarfile_backport(work, expected)
    assert module.read_bytes() == b"unpatched-runtime"
    assert not (work / "tarfile-remediation.json").exists()


def test_backport_verification_rechecks_candidate_after_regression(
    clock_tools, bundle, monkeypatch,
):
    work, expected = bundle

    def changed_during_run(*args, **kwargs):
        (work / "bundle" / clock_tools.TARFILE_PATH).write_bytes(b"changed")
        return json.dumps({"state": "VENDOR_BACKPORT_VERIFIED", "cve": "CVE-2026-82049",
                           "filters": ["data", "tar"]})

    monkeypatch.setattr(clock_tools, "run", changed_during_run)
    with pytest.raises(ValueError, match="digest"):
        clock_tools.verify_tarfile_backport(work, expected)
    assert not (work / "tarfile-remediation.json").exists()


@settings(max_examples=2000, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(field=st.sampled_from(["cve", "upstreamCommit", "file", "beforeSha256", "afterSha256"]),
       value=st.one_of(st.none(), st.integers(min_value=-1, max_value=2**32),
                       st.binary(min_size=1, max_size=32).map(bytes.hex)),
       mutation=st.sampled_from(["replace", "remove", "extra"]))
def test_property_patch_identity_cannot_be_redefined_by_reviewed_json(
    clock_tools, bundle, field, value, mutation,
):
    # Reset the whole document each example; the shared payload is read-only throughout.
    work, _ = bundle
    path = work / "bundle.json"
    manifest = json.loads(path.read_bytes())
    manifest["runtimePatch"] = clock_tools.runtime_patch()
    data = clock_tools.json_bytes(manifest)
    path.write_bytes(data)
    assert clock_tools.verify_bundle(work, clock_tools.fingerprint(data)) == manifest
    if mutation == "remove":
        del manifest["runtimePatch"][field]
    else:
        if value == manifest["runtimePatch"][field]:
            value += "0"
        manifest["runtimePatch"][field if mutation == "replace" else "extra"] = value
    data = clock_tools.json_bytes(manifest)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="runtime patch"):
        clock_tools.verify_bundle(work, clock_tools.fingerprint(data))


def test_snapshot_and_copy_refuse_symlinks_and_fifos(clock_tools, tmp_path):
    value = tmp_path / "value"
    value.write_bytes(b"content")
    link = tmp_path / "link"
    link.symlink_to(value)
    with pytest.raises(OSError):
        clock_tools.read_regular(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="unsafe"):
        clock_tools.read_regular(fifo)


def test_immutable_installer_preserves_foreign_existing_files(clock_tools, tmp_path):
    file = tmp_path / "artifact"
    file.write_bytes(b"existing-user-work")
    with pytest.raises(PermissionError):
        clock_tools.install_file(file, b"replacement")
    assert file.read_bytes() == b"existing-user-work"
    fresh = tmp_path / "new"
    clock_tools.install_file(fresh, b"frozen", executable=True)
    assert fresh.read_bytes() == b"frozen"
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o555


def test_chrony_socket_budget_includes_the_clients_private_path(clock_tools):
    with pytest.raises(ValueError, match="socket path"):
        clock_tools.observer_config(Path("/" + "a" * 75))
    config = clock_tools.observer_config(clock_tools.SOCKET_ROOT).decode()
    assert "authselectmode require" in config and "port 0" in config
    assert "user _docsuri_r1t_clock" in config


def test_live_load_check_uses_executable_maps_and_resolves_os_path_aliases(clock_tools, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "chronyd").write_bytes(b"fixture")
    alias = tmp_path / "alias"
    alias.symlink_to(bundle, target_is_directory=True)
    maps = (f"__TEXT 100-200 [16K] r-x/rwx SM=COW {alias}/chronyd\n"
            "mapped file 200-300 [4K] r--/r-- SM=COW /private/var/db/diagnostics/logd/data\n"
            "__TEXT 300-400 [4K] r-x/r-x SM=COW /usr/lib/libSystem.B.dylib\n")
    assert clock_tools.verify_live_images(maps, bundle) == 2
    other = tmp_path / "outside.dylib"
    other.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="unfrozen"):
        clock_tools.verify_live_images(
            maps + f"__TEXT 500-600 [4K] r-x/r-x SM=COW {other}\n", bundle,
        )


def test_operator_script_parses_on_system_python_39():
    import ast

    ast.parse(SCRIPT.read_text(), feature_version=(3, 9))


def pinned_archive(clock_tools, module):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as stream:
        item = tarfile.TarInfo("python/lib/python3.13/tarfile.py")
        item.size = len(module)
        stream.addfile(item, io.BytesIO(module))
    return output.getvalue()


@pytest.fixture
def backport(clock_tools, tmp_path, monkeypatch):
    work = tmp_path / "work"
    module = work / "bundle/runtime/lib/python3.13/tarfile.py"
    module.parent.mkdir(parents=True)
    original = b"def makelink(self):\n" + VENDOR_PREIMAGE + b"\n    return None\n"
    module.write_bytes(original)
    monkeypatch.setattr(clock_tools, "TARFILE_BEFORE_SHA", hashlib.sha256(original).hexdigest())
    patched = original.replace(VENDOR_PREIMAGE, VENDOR_POSTIMAGE)
    monkeypatch.setattr(clock_tools, "TARFILE_AFTER_SHA", hashlib.sha256(patched).hexdigest())
    monkeypatch.setattr(clock_tools, "download",
                        lambda url, expected, destination: pinned_archive(clock_tools, original))
    return clock_tools, work, module, original


def test_vendor_backport_applies_exactly_the_upstream_hardlink_fix(backport):
    clock_tools, work, module, original = backport
    proof = clock_tools.apply_tarfile_backport(work)
    assert proof["cve"] == "CVE-2026-82049"
    assert proof["beforeSha256"] == hashlib.sha256(original).hexdigest()
    assert b"os.path.realpath(tarinfo._link_target)" in module.read_bytes()
    assert proof["afterSha256"] == hashlib.sha256(module.read_bytes()).hexdigest()


def test_vendor_backport_is_idempotent_across_reseals(backport):
    clock_tools, work, module, original = backport
    first = clock_tools.apply_tarfile_backport(work)
    assert clock_tools.apply_tarfile_backport(work) == first
    assert module.read_bytes().count(b"os.link(os.path.realpath(tarinfo._link_target)") == 1


def test_vendor_backport_refuses_a_staged_module_it_did_not_pin(backport):
    clock_tools, work, module, original = backport
    module.write_bytes(b"attacker supplied runtime\n" + VENDOR_PREIMAGE)
    with pytest.raises(ValueError, match="unrecognized staged tarfile module"):
        clock_tools.apply_tarfile_backport(work)


def test_vendor_backport_refuses_a_vendor_preimage_it_cannot_verify(backport):
    clock_tools, work, module, original = backport
    monkeypatched = b"                    os.link(tarinfo.linkname, targetpath)"
    module.write_bytes(monkeypatched)
    clock_tools.download = lambda url, expected, destination: pinned_archive(
        clock_tools, monkeypatched,
    )
    with pytest.raises(ValueError, match="preimage differs"):
        clock_tools.apply_tarfile_backport(work)


def test_vendor_backport_drops_stale_bytecode_for_the_patched_module(backport):
    clock_tools, work, module, original = backport
    cache = module.parent / "__pycache__"
    cache.mkdir()
    stale = cache / "tarfile.cpython-313.pyc"
    stale.write_bytes(b"stale bytecode")
    clock_tools.apply_tarfile_backport(work)
    assert not stale.exists()


def test_vendor_backport_refuses_privileged_execution(backport, monkeypatch):
    clock_tools, work, module, original = backport
    monkeypatch.setattr(clock_tools.os, "geteuid", lambda: 0)
    with pytest.raises(PermissionError):
        clock_tools.apply_tarfile_backport(work)


@settings(max_examples=2000, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(commands=st.lists(st.sampled_from(["apply", "verify", "corrupt"]), max_size=20))
def test_property_backport_state_model_never_repairs_foreign_bytes(backport, commands):
    clock_tools, work, module, original = backport
    module.write_bytes(original)  # Reset fixture per generated sequence, including empty sequences.
    state = "base"
    for command in commands:
        before = module.read_bytes()
        if command == "corrupt":
            module.write_bytes(b"foreign-bytes")
            state = "foreign"
        elif command == "apply":
            if state == "foreign":
                with pytest.raises(ValueError, match="unrecognized staged"):
                    clock_tools.apply_tarfile_backport(work)
                assert module.read_bytes() == before
            else:
                clock_tools.apply_tarfile_backport(work)
                assert module.read_bytes() == original.replace(VENDOR_PREIMAGE, VENDOR_POSTIMAGE)
                if state == "fixed":
                    assert module.read_bytes() == before
                state = "fixed"
        else:
            if state == "fixed":
                clock_tools.verify_runtime_patch(work / "bundle", clock_tools.runtime_patch())
            else:
                with pytest.raises(ValueError, match="postimage"):
                    clock_tools.verify_runtime_patch(work / "bundle", clock_tools.runtime_patch())
            assert module.read_bytes() == before


def test_bootstrap_extraction_never_materializes_a_hard_link(clock_tools, tmp_path):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as stream:
        link = tarfile.TarInfo("source/b")
        link.type, link.linkname = tarfile.LNKTYPE, "source/a"
        stream.addfile(link)
    with pytest.raises(ValueError, match="unsupported archive member"):
        clock_tools.extract_archive(output.getvalue(), tmp_path / "extract", "source")
    assert not (tmp_path / "extract").exists()


# --- regression: pinned bytecode bricked the installed clock deployment ---------------
#
# The clock-sample entry shipped as `python -I -m docsuri_platform_integrity.host` with no -B.
# The first run rewrote four stdlib .pyc files (encodings/__init__, aliases, utf_8, linecache)
# in the frozen closure; the manifest had pinned their digests, so every later run died in
# execute()'s artifact check with "frozen artifact verification failed" before chronyc was
# ever invoked. Nothing recovered without a rebuild, and the nts-observer could no longer
# restart either. The trigger was any interpreter run against the closure without -B.


def test_every_shipped_host_invocation_disables_bytecode_writes():
    # Applies to the generated entry and to the publisher's expected_launch alike. These must
    # agree, or the build rejects its own bundle, so the invariant is checked over the source.
    source = (Path(__file__).resolve().parents[1] / "platform-integrity"
              / "provision_clock.py").read_text()
    offending = [line.strip() for line in source.splitlines()
                 if '"-m","docsuri_platform_integrity' in line and '"-B"' not in line]
    assert not offending, offending


def test_bytecode_is_never_pinned_as_a_deployment_artifact(clock_tools):
    # freeze_tree keeps .pyc out of the tree; the manifest must keep it out of the artifact set
    # too, or the tree can be clean and the manifest still bricked.
    assert clock_tools.pinned_artifact("runtime/lib/python3.13/linecache.py")
    for path in ("runtime/lib/python3.13/__pycache__/linecache.cpython-313.pyc",
                 "runtime/lib/python3.13/encodings/__pycache__/utf_8.cpython-313.pyc",
                 "native/chronyc.pyc", "runtime/lib/python3.13/foo.pyo"):
        assert not clock_tools.pinned_artifact(path), path
