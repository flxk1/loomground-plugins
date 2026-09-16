import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ecosystem_certify  # noqa: E402
import ecosystem_parity_matrix as parity  # noqa: E402


@pytest.fixture(scope="module")
def matrix():
    return parity.build_matrix()


@pytest.fixture(scope="module")
def manifest():
    return parity.load_manifest()


@pytest.fixture(scope="module")
def names(manifest):
    return parity.manifest_names(manifest)


@pytest.fixture(scope="module")
def catalogue():
    return parity.load_catalogue()


@pytest.fixture(scope="module")
def skills_index():
    return parity.load_skills_index()


@pytest.fixture(scope="module")
def marketplace():
    return parity.load_marketplace()


@pytest.fixture(scope="module")
def roles():
    return parity.load_roles()


# --- row set -----------------------------------------------------------

def test_row_count_is_exactly_41(matrix):
    assert matrix["row_count"] == 41
    assert len(matrix["rows"]) == 41


def test_rows_match_manifest_names_exactly(matrix, names):
    row_names = sorted(row["name"] for row in matrix["rows"])
    assert row_names == names
    assert len(set(row_names)) == 41


def test_manifest_names_rejects_wrong_count():
    manifest = {"repositories": [{"name": f"repo-{i}"} for i in range(40)]}
    with pytest.raises(parity.ParityError, match="exactly 41"):
        parity.manifest_names(manifest)


def test_manifest_names_rejects_duplicates():
    manifest = {"repositories": [{"name": "a"}] * 41}
    with pytest.raises(parity.ParityError, match="exactly 41"):
        parity.manifest_names(manifest)


# --- schema ---------------------------------------------------------

def test_matrix_is_schema_valid(matrix):
    schema = ecosystem_certify.load_json(ROOT / "schemas/parity-matrix.schema.json")
    Draft202012Validator(schema).validate(matrix)


def test_matrix_is_deterministic():
    first = parity.build_matrix()
    second = parity.build_matrix()
    assert first == second


def test_matrix_sha256_is_self_consistent(matrix):
    payload = copy.deepcopy(matrix)
    del payload["matrix_sha256"]
    assert ecosystem_certify.digest(payload) == matrix["matrix_sha256"]


# --- cell shape / honesty -----------------------------------------------

def test_every_cell_carries_present_value_reason(matrix):
    for row in matrix["rows"]:
        for column in ("mcp_tool", "installable_skill", "plugin_source", "agent_role"):
            field = row[column]
            assert set(field) == {"present", "value", "reason"}
            if field["present"]:
                assert field["reason"] is None
                assert field["value"] is not None
            else:
                assert field["value"] is None
                assert isinstance(field["reason"], str) and field["reason"]


def test_at_least_one_legitimate_null_per_column(matrix):
    for column in ("mcp_tool", "installable_skill", "plugin_source"):
        nulls = [row for row in matrix["rows"] if not row[column]["present"]]
        assert nulls, f"expected at least one legitimate null cell in {column}"
    # agent_role is a total partition: every repository always resolves to exactly one role
    assert all(row["agent_role"]["present"] for row in matrix["rows"])


def test_a2a_compliance_repository_has_mcp_tool_and_skill_and_plugin_and_role(matrix):
    row = next(r for r in matrix["rows"] if r["name"] == "a2a-compliance")
    assert row["mcp_tool"]["present"] and "a2a_plan" in row["mcp_tool"]["value"]
    assert row["installable_skill"]["present"] and row["installable_skill"]["value"] == ["compliance-fleet"]
    assert row["plugin_source"]["present"] and row["plugin_source"]["value"]["url"].endswith("a2a-compliance.git")
    assert row["agent_role"]["present"] and row["agent_role"]["value"] == "conductor"


def test_5d_nd_has_a_legitimate_null_installable_skill_with_reason(matrix):
    row = next(r for r in matrix["rows"] if r["name"] == "5d-nd")
    assert row["installable_skill"]["present"] is False
    assert row["installable_skill"]["value"] is None
    assert "no public installable skill" in row["installable_skill"]["reason"]
    # but the row is not otherwise blank: it still has a tool and a role
    assert row["mcp_tool"]["present"] is True
    assert row["agent_role"]["present"] is True


def test_loomground_governance_has_a_legitimate_null_mcp_tool_with_reason(matrix):
    row = next(r for r in matrix["rows"] if r["name"] == "loomground-governance")
    assert row["mcp_tool"]["present"] is False
    assert "no MCP tool is declared" in row["mcp_tool"]["reason"]


def test_loomground_workspace_has_a_legitimate_null_plugin_source_with_reason(matrix):
    row = next(r for r in matrix["rows"] if r["name"] == "loomground-workspace")
    assert row["plugin_source"]["present"] is False
    assert "not listed as a pinned external plugin source" in row["plugin_source"]["reason"]


def test_agent_role_partitions_all_41_repositories_across_8_roles(matrix):
    role_ids = {row["agent_role"]["value"] for row in matrix["rows"]}
    assert role_ids == set(parity.ROLE_IDS)
    per_role = {}
    for row in matrix["rows"]:
        per_role.setdefault(row["agent_role"]["value"], []).append(row["name"])
    assert sum(len(v) for v in per_role.values()) == 41
    assert per_role["decision-verifier"] == ["loomground-solver"]


# --- markdown -------------------------------------------------------

def test_markdown_renders_one_row_per_repository(matrix):
    rendered = parity.render_markdown(matrix)
    for row in matrix["rows"]:
        assert f"| {row['name']} |" in rendered


# --- fail-closed: catalogue / row-set drift ------------------------------

def test_catalogue_rejects_missing_repository(names, catalogue):
    trimmed = copy.deepcopy(catalogue)
    trimmed["repos"] = [r for r in trimmed["repos"] if r["repo"] != "5d-nd"]
    with pytest.raises(parity.ParityError, match="differ from the ecosystem inventory"):
        parity.catalogue_repo_tools(trimmed, names)


def test_catalogue_rejects_extra_repository(names, catalogue):
    extended = copy.deepcopy(catalogue)
    extended["repos"].append({"repo": "not-a-real-repo", "tools": [], "skills": []})
    with pytest.raises(parity.ParityError, match="differ from the ecosystem inventory"):
        parity.catalogue_repo_tools(extended, names)


def test_catalogue_rejects_duplicate_repository(names, catalogue):
    duplicated = copy.deepcopy(catalogue)
    duplicated["repos"].append(dict(duplicated["repos"][0]))
    with pytest.raises(parity.ParityError, match="repeats a repository"):
        parity.catalogue_repo_tools(duplicated, names)


def test_catalogue_rejects_a_tool_owned_by_two_repositories(catalogue):
    mutated = copy.deepcopy(catalogue)
    donor = next(r for r in mutated["repos"] if r["tools"])
    victim = next(r for r in mutated["repos"] if r is not donor)
    victim["tools"] = list(victim["tools"]) + [donor["tools"][0]]
    with pytest.raises(parity.ParityError, match="assigns one tool to more than one repository"):
        parity.build_tool_and_skill_maps(mutated)


# --- fail-closed: installable skill drift ------------------------------

def test_skills_index_rejects_public_entry_for_unknown_repository(names, skills_index):
    injected = copy.deepcopy(skills_index)
    injected.append({"repo": "not-a-real-repo", "name": "ghost-skill", "allowed_tools": []})
    with pytest.raises(parity.ParityError, match="unknown repository"):
        parity.installable_skill_cells(injected, names)


def test_skills_index_rejects_private_flag_on_an_inventory_repository(names, skills_index):
    mutated = copy.deepcopy(skills_index)
    entry = next(e for e in mutated if e["repo"] == "privacy-shield")
    entry["private"] = True
    with pytest.raises(parity.ParityError, match="marks a 41-inventory repository private"):
        parity.installable_skill_cells(mutated, names)


# --- fail-closed: plugin source drift ------------------------------

def test_marketplace_rejects_external_pin_outside_inventory(names, marketplace):
    mutated = copy.deepcopy(marketplace)
    mutated["plugins"].append({
        "name": "not-a-real-repo",
        "source": {"source": "url", "url": "https://github.com/flxk1/not-a-real-repo.git", "sha": "0" * 40},
    })
    with pytest.raises(parity.ParityError, match="outside the ecosystem inventory"):
        parity.plugin_source_cells(mutated, names)


# --- fail-closed: agent/role drift ------------------------------

def test_roles_reject_capability_referencing_unknown_repository(names, catalogue, roles):
    mutated = copy.deepcopy(roles)
    mutated["conductor"]["allowed_capabilities"] = list(mutated["conductor"]["allowed_capabilities"]) + [
        "contract:not-a-real-repo"
    ]
    with pytest.raises(parity.ParityError, match="outside the ecosystem inventory"):
        parity.agent_role_cells(mutated, catalogue, names)


def test_roles_reject_a_repository_dropped_from_every_role(names, catalogue, roles):
    mutated = copy.deepcopy(roles)
    for role in mutated.values():
        role["allowed_capabilities"] = [
            cap for cap in role["allowed_capabilities"] if cap != "contract:loomground-workspace"
        ]
    with pytest.raises(parity.ParityError, match="do not exactly cover the ecosystem inventory"):
        parity.agent_role_cells(mutated, catalogue, names)


def test_roles_reject_a_repository_claimed_by_two_roles(names, catalogue, roles):
    mutated = copy.deepcopy(roles)
    mutated["assurance-recorder"]["allowed_capabilities"] = list(
        mutated["assurance-recorder"]["allowed_capabilities"]
    ) + ["contract:loomground-workspace"]
    with pytest.raises(parity.ParityError, match="assigned to more than one role"):
        parity.agent_role_cells(mutated, catalogue, names)


def test_roles_reject_unrecognised_capability_kind(names, catalogue, roles):
    mutated = copy.deepcopy(roles)
    mutated["conductor"]["allowed_capabilities"] = list(mutated["conductor"]["allowed_capabilities"]) + [
        "mystery:something"
    ]
    with pytest.raises(parity.ParityError, match="unrecognised capability kind"):
        parity.agent_role_cells(mutated, catalogue, names)


def test_roles_reject_wrong_role_count(names, catalogue, roles):
    mutated = copy.deepcopy(roles)
    del mutated["conductor"]
    with pytest.raises(parity.ParityError, match="do not exactly cover the ecosystem inventory"):
        parity.agent_role_cells(mutated, catalogue, names)


# --- cell() construction guards -------------------------------------------

def test_cell_helper_rejects_inconsistent_arguments():
    with pytest.raises(parity.ParityError):
        parity.cell(True, value="x", reason="not allowed alongside present")
    with pytest.raises(parity.ParityError):
        parity.cell(False, value="not allowed", reason="ok")
    with pytest.raises(parity.ParityError):
        parity.cell(False, reason="")


# --- CLI: --check mode, fail-closed on drift ------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/ecosystem_parity_matrix.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_check_mode_passes_against_the_committed_artifact():
    result = run_cli("--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHECK PASS" in result.stdout


def test_check_mode_fails_when_the_artifact_is_missing(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    result = run_cli("--check", "--output", str(missing))
    assert result.returncode != 0
    assert "missing" in result.stdout


def test_check_mode_fails_on_a_mutated_committed_cell(tmp_path):
    committed = (ROOT / "ecosystem/parity-matrix.json").read_bytes()
    mutated = json.loads(committed)
    mutated["rows"][0]["agent_role"]["value"] = "not-a-real-role"
    stale = tmp_path / "parity-matrix.json"
    stale.write_bytes(ecosystem_certify.canonical_json(mutated) + b"\n")
    result = run_cli("--check", "--output", str(stale))
    assert result.returncode != 0
    assert "stale" in result.stdout


def test_check_mode_fails_on_a_stale_markdown(tmp_path):
    stale_md = tmp_path / "parity-matrix.md"
    stale_md.write_text("stale content that will never match\n", encoding="utf-8")
    result = run_cli("--check", "--markdown", str(stale_md))
    assert result.returncode != 0
    assert "markdown is stale" in result.stdout


def test_generate_mode_writes_json_and_markdown(tmp_path):
    output = tmp_path / "generated.json"
    markdown = tmp_path / "generated.md"
    result = run_cli("--output", str(output), "--markdown", str(markdown))
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.is_file() and markdown.is_file()
    regenerated = json.loads(output.read_bytes())
    committed = json.loads((ROOT / "ecosystem/parity-matrix.json").read_bytes())
    assert regenerated == committed
