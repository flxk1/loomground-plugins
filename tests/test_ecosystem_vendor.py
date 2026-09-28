import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ecosystem_vendor as vendor  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="module")
def manifest():
    return vendor.load_manifest()


def make_fixture_fetcher(catalogue, roles, skills_index):
    """Build an offline Fetcher over an in-memory fixture, keyed by (repo, path)."""

    def fetcher(repo: str, commit: str, path: str) -> bytes:
        if repo == vendor.CATALOGUE_SOURCE_REPO and path == vendor.CATALOGUE_SOURCE_PATH:
            return json.dumps(catalogue).encode("utf-8")
        if repo == vendor.SKILLS_INDEX_SOURCE_REPO and path == vendor.SKILLS_INDEX_SOURCE_PATH:
            return json.dumps(skills_index).encode("utf-8")
        if repo == vendor.ROLES_SOURCE_REPO and path.startswith(vendor.ROLES_SOURCE_DIR + "/"):
            role_id = path.rsplit("/", 1)[-1].removesuffix(".json")
            if role_id in roles:
                return json.dumps(roles[role_id]).encode("utf-8")
        raise AssertionError(f"fixture fetcher has no content for {repo}:{path}")

    return fetcher


def minimal_catalogue():
    return {"family": "Loomground", "source": "CATALOGUE.md", "url_base": "https://github.com/flxk1/", "repos": []}


def minimal_roles():
    return {
        role_id: {
            "id": role_id,
            "identity": f"a2a-compliance/{role_id}",
            "allowed_capabilities": [],
        }
        for role_id in vendor.ROLE_IDS
    }


def minimal_skills_index(names):
    # One legitimate in-inventory record, one private record, one out-of-inventory
    # record, so the projection test has something real to drop.
    return [
        {"repo": sorted(names)[0], "name": "public-one", "description": "d", "commit": "a" * 40, "path": "skills/a/SKILL.md"},
        {"repo": sorted(names)[0], "name": "private-one", "description": "d", "commit": "a" * 40, "path": "skills/b/SKILL.md", "private": True},
        {"repo": "some-unlisted-private-repo", "name": "leaked-one", "description": "d", "commit": "a" * 40, "path": "skills/c/SKILL.md"},
    ]


def test_public_projection_drops_private_and_out_of_inventory_records(manifest):
    names = vendor.manifest_names(manifest)
    entries = minimal_skills_index(names)
    projected = vendor.public_projection(entries, names)
    projected_names = {(entry["repo"], entry["name"]) for entry in projected}
    assert (sorted(names)[0], "public-one") in projected_names
    assert (sorted(names)[0], "private-one") not in projected_names
    assert ("some-unlisted-private-repo", "leaked-one") not in projected_names
    assert len(projected) == 1


def test_build_artifacts_offline_matches_fixture(manifest):
    names = vendor.manifest_names(manifest)
    catalogue = minimal_catalogue()
    roles = minimal_roles()
    skills_index = minimal_skills_index(names)
    fetcher = make_fixture_fetcher(catalogue, roles, skills_index)

    artifacts = vendor.build_artifacts(manifest, fetcher)

    assert artifacts[vendor.CATALOGUE_PATH] == vendor.pretty_json_bytes(catalogue)
    expected_projection = vendor.public_projection(skills_index, names)
    assert artifacts[vendor.SKILLS_INDEX_PATH] == vendor.pretty_json_bytes(expected_projection)
    for role_id in vendor.ROLE_IDS:
        path = vendor.ROLES_DIR / f"{role_id}.json"
        assert artifacts[path] == vendor.pretty_json_bytes(roles[role_id])
    assert artifacts[vendor.PINS_PATH] == vendor.build_pins_document()


def test_build_artifacts_rejects_malformed_catalogue(manifest):
    catalogue = {"family": "NotLoomground", "repos": []}
    roles = minimal_roles()
    skills_index = minimal_skills_index(vendor.manifest_names(manifest))
    fetcher = make_fixture_fetcher(catalogue, roles, skills_index)
    with pytest.raises(vendor.VendorError):
        vendor.build_artifacts(manifest, fetcher)


def test_build_artifacts_rejects_malformed_role(manifest):
    catalogue = minimal_catalogue()
    roles = minimal_roles()
    roles["conductor"]["id"] = "not-conductor"
    skills_index = minimal_skills_index(vendor.manifest_names(manifest))
    fetcher = make_fixture_fetcher(catalogue, roles, skills_index)
    with pytest.raises(vendor.VendorError):
        vendor.build_artifacts(manifest, fetcher)


def test_run_check_passes_when_artifacts_match_fixture(manifest, tmp_path, monkeypatch):
    names = vendor.manifest_names(manifest)
    catalogue = minimal_catalogue()
    roles = minimal_roles()
    skills_index = minimal_skills_index(names)
    fetcher = make_fixture_fetcher(catalogue, roles, skills_index)

    catalogue_path = tmp_path / "catalogue.json"
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    skills_index_path = tmp_path / "skills-index.json"
    pins_path = tmp_path / "PINS.json"

    monkeypatch.setattr(vendor, "CATALOGUE_PATH", catalogue_path)
    monkeypatch.setattr(vendor, "SKILLS_INDEX_PATH", skills_index_path)
    monkeypatch.setattr(vendor, "ROLES_DIR", roles_dir)
    monkeypatch.setattr(vendor, "PINS_PATH", pins_path)
    monkeypatch.setattr(vendor, "load_manifest", lambda: manifest)

    assert vendor.run(fetcher, check=False) == 0
    assert vendor.run(fetcher, check=True) == 0


def test_run_check_fails_on_a_tampered_copy(manifest, tmp_path, monkeypatch):
    names = vendor.manifest_names(manifest)
    catalogue = minimal_catalogue()
    roles = minimal_roles()
    skills_index = minimal_skills_index(names)
    fetcher = make_fixture_fetcher(catalogue, roles, skills_index)

    catalogue_path = tmp_path / "catalogue.json"
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    skills_index_path = tmp_path / "skills-index.json"
    pins_path = tmp_path / "PINS.json"

    monkeypatch.setattr(vendor, "CATALOGUE_PATH", catalogue_path)
    monkeypatch.setattr(vendor, "SKILLS_INDEX_PATH", skills_index_path)
    monkeypatch.setattr(vendor, "ROLES_DIR", roles_dir)
    monkeypatch.setattr(vendor, "PINS_PATH", pins_path)
    monkeypatch.setattr(vendor, "load_manifest", lambda: manifest)

    assert vendor.run(fetcher, check=False) == 0

    # Tamper with a committed vendored artifact after a clean vendor.
    catalogue_path.write_bytes(catalogue_path.read_bytes() + b"tampered")

    assert vendor.run(fetcher, check=True) == 1


def test_role_ids_come_from_the_shared_parity_module():
    """ecosystem_vendor must not grow a second, drifting copy of the role inventory."""
    import ecosystem_parity_matrix as parity

    assert vendor.ROLE_IDS is parity.ROLE_IDS
