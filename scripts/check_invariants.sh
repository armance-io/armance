#!/usr/bin/env bash
# check_invariants.sh — verifies the 6 future-web invariants from docs/spec/23_future_web_layer.md
#
# Run after every commit during the remediation sprints (R-01..R-08). Exit code 0 = clean. Exit code 1 = at least one violation.
#
# Each invariant has its own check function; failures are reported with file:line context so the offending location is immediately actionable.
#
# This script is the safety net for an LLM agent working autonomously. It is intentionally strict — false positives are easier to triage than missed violations.

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
cd "$REPO_ROOT"

# Colors only on TTY
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BOLD=''; NC=''
fi

VIOLATIONS=0
INVARIANTS_OK=0

# Paths scanned: src/ and tests/ but NOT docs/ (specs reference legacy names by design)
# and NOT .archive/ or wip/ (parked legacy is allowed to use legacy names).
SCAN_GLOB="src/ tests/"
EXCLUDE_PATHS=(
    "*/.archive/*"
    "*/wip/*"
    "*/armance_web/*"
    "*/legacy*"
    "*/builtin_agents/*"      # legacy templates, replaced by service/agents/builtin/
    "*/backend"               # web transport adapter: wire-format uses these strings by design
)

# Build grep exclude args
GREP_EXCLUDE_ARGS=()
for p in "${EXCLUDE_PATHS[@]}"; do
    GREP_EXCLUDE_ARGS+=(--exclude-dir="${p#*/}")
done

# Helpers ----------------------------------------------------------------

header() {
    echo ""
    echo -e "${BOLD}--- $1 ---${NC}"
}

ok() {
    echo -e "${GREEN}✓${NC} $1"
    INVARIANTS_OK=$((INVARIANTS_OK + 1))
}

fail() {
    echo -e "${RED}✗ VIOLATION:${NC} $1"
    VIOLATIONS=$((VIOLATIONS + 1))
}

note() {
    echo -e "${YELLOW}  note:${NC} $1"
}

# Pretty-print grep hits (max 10)
show_hits() {
    local file="$1"
    local hits
    hits=$(head -n 10 "$file")
    if [ -n "$hits" ]; then
        echo "$hits" | sed 's/^/    /'
        local total
        total=$(wc -l < "$file")
        if [ "$total" -gt 10 ]; then
            note "(showing 10 of $total)"
        fi
    fi
}

# ========================================================================
# INVARIANT 1 — Workflow / Task lifecycle states follow A2A
# Forbidden: "pending", "running", "done", "aborted" as state strings.
# Allowed inside docstrings or comments mentioning legacy migration ONLY in
# files that explicitly do migration (search keyword "migration" in same file).
# ========================================================================

check_invariant_1() {
    header "Invariant 1 — A2A lifecycle states"

    local tmpfile
    tmpfile=$(mktemp)

    # Scan for forbidden state strings in code (not docstrings)
    # Patterns: status: "pending", state == "running", "done", "aborted" in dict/yaml/enum contexts
    grep -rn -E '("|'"'"')(pending|running|done|aborted)("|'"'"')' \
        --include="*.py" --include="*.yaml" --include="*.yml" \
        "${GREP_EXCLUDE_ARGS[@]}" \
        $SCAN_GLOB 2>/dev/null \
        | grep -vE '#.*(legacy|migration|deprecated|TODO|FIXME|backwards.compat)' \
        | grep -vE 'test_(meeting|judge|legacy)' \
        | grep -vE '("|'"'"')(running|done)("|'"'"')\s*[:,)]?\s*#.*test' \
        > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "forbidden lifecycle state strings (pending/running/done/aborted) found"
        note "use submitted | working | input-required | completed | failed | canceled | serge_inconclusive"
        show_hits "$tmpfile"
    else
        ok "no legacy state strings in source"
    fi

    # Also forbid these strings in Python Literal type annotations
    > "$tmpfile"
    grep -rn -E 'Literal\[.*"(pending|running|done|aborted)".*\]' \
        --include="*.py" "${GREP_EXCLUDE_ARGS[@]}" \
        $SCAN_GLOB 2>/dev/null > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "Literal type still includes legacy state names"
        show_hits "$tmpfile"
    else
        ok "no Literal type annotations with legacy states"
    fi

    rm -f "$tmpfile"
}

# ========================================================================
# INVARIANT 2 — Agent Card sidecars
# Every .md agent file (system + specialist) must trigger generation
# of .agent_card.json on RosterService.refresh().
# Check: RosterService class references agent_card; agent_card_path helper exists.
# ========================================================================

check_invariant_2() {
    header "Invariant 2 — agent_card.json sidecars"

    if grep -rqn "agent_card_path\|agent_card\.json" src/armance/storage/paths.py 2>/dev/null; then
        ok "agent_card_path helper present in storage/paths.py"
    else
        fail "agent_card_path missing from storage/paths.py"
    fi

    if grep -rqn "agent_card" src/armance/service/shared_memory_service.py 2>/dev/null || \
       grep -rqn "agent_card" src/armance/service/roster_service.py 2>/dev/null; then
        ok "agent_card generation wired in RosterService"
    else
        fail "RosterService.refresh() does not generate agent_card.json sidecars"
        note "expected: a function that reads agents/<n>.md frontmatter and writes agents/<n>.agent_card.json"
    fi
}

# ========================================================================
# INVARIANT 3 — Skills carry MCP-shape metadata
# Every Skill subclass must declare description, input_schema, output_schema.
# Check: base class has these fields; spot-check 3 skills.
# ========================================================================

check_invariant_3() {
    header "Invariant 3 — Skill MCP shape"

    local base_file="src/armance/service/skills/base.py"
    if [ ! -f "$base_file" ]; then
        fail "service/skills/base.py missing"
        return
    fi

    if grep -qn "description\s*:" "$base_file" && \
       grep -qn "input_schema\s*:" "$base_file" && \
       grep -qn "output_schema\s*:" "$base_file"; then
        ok "Skill base class declares description / input_schema / output_schema"
    else
        fail "Skill base class missing one or more of: description, input_schema, output_schema"
        note "see docs/spec/18_command_nl_bridge.md § Skill contract"
    fi

    # Spot-check 3 skills
    local skill_files
    skill_files=$(find src/armance/service/skills/ -name "*.py" ! -name "base.py" ! -name "__init__.py" -type f 2>/dev/null | head -3)
    local missing=0
    for f in $skill_files; do
        if ! grep -qn "input_schema" "$f"; then
            fail "skill $f does not declare input_schema"
            missing=$((missing + 1))
        fi
    done
    if [ "$missing" -eq 0 ] && [ -n "$skill_files" ]; then
        ok "spot-checked skills declare input_schema"
    fi
}

# ========================================================================
# INVARIANT 4 — sqlite-vec, not Chroma
# Forbidden: any import of chromadb. rag_chroma.py must be gone.
# ========================================================================

check_invariant_4() {
    header "Invariant 4 — sqlite-vec (no Chroma)"

    local tmpfile
    tmpfile=$(mktemp)

    grep -rn -E "^(from chromadb|import chromadb)" \
        --include="*.py" "${GREP_EXCLUDE_ARGS[@]}" \
        $SCAN_GLOB 2>/dev/null > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "chromadb is still imported"
        show_hits "$tmpfile"
    else
        ok "no chromadb imports"
    fi

    if [ -f "src/armance/storage/rag_chroma.py" ]; then
        fail "src/armance/storage/rag_chroma.py still exists; must be deleted"
    else
        ok "rag_chroma.py deleted"
    fi

    if grep -qE '^\s*"chromadb' pyproject.toml 2>/dev/null; then
        fail "chromadb still in pyproject.toml dependencies"
    else
        ok "chromadb removed from pyproject.toml"
    fi

    if grep -qE '"sqlite-vec' pyproject.toml 2>/dev/null; then
        ok "sqlite-vec present in pyproject.toml"
    else
        fail "sqlite-vec missing from pyproject.toml"
    fi

    if [ -f "src/armance/storage/rag_index.py" ]; then
        ok "storage/rag_index.py present (sqlite-vec backend lives in storage)"
    else
        fail "storage/rag_index.py missing"
    fi

    rm -f "$tmpfile"
}

# ========================================================================
# INVARIANT 5 — OpenTelemetry-shaped Events
# core/models/event.py exists with Event dataclass (trace_id, span_id, ...)
# service/events.py exists with EventBus protocol + LocalEventBus impl.
# ========================================================================

check_invariant_5() {
    header "Invariant 5 — OpenTelemetry event shape"

    if [ -f "src/armance/core/models/event.py" ]; then
        if grep -qn "trace_id" src/armance/core/models/event.py && \
           grep -qn "span_id" src/armance/core/models/event.py && \
           grep -qn "attributes" src/armance/core/models/event.py; then
            ok "core/models/event.py declares OTel-shaped Event (trace_id, span_id, attributes)"
        else
            fail "core/models/event.py exists but missing OTel fields (trace_id / span_id / attributes)"
        fi
    else
        fail "core/models/event.py missing"
    fi

    if [ -f "src/armance/service/events.py" ]; then
        # After J.3, service/events.py is a shim; the classes live in platform/events.py.
        # Accept either the old layout (class in service) or the new layout (shim + class in platform).
        if grep -qn "class EventBus\|class LocalEventBus" src/armance/service/events.py; then
            ok "service/events.py declares EventBus / LocalEventBus"
        elif grep -qn "class EventBus\|class LocalEventBus" src/armance/platform/events.py 2>/dev/null \
             && grep -qn "from armance.platform.events import" src/armance/service/events.py; then
            ok "service/events.py is a shim; EventBus / LocalEventBus declared in platform/events.py"
        else
            fail "service/events.py exists but does not declare EventBus / LocalEventBus (nor shim to platform)"
        fi
    else
        fail "service/events.py missing"
    fi

    # Forbid ad-hoc event dicts in service code
    local tmpfile
    tmpfile=$(mktemp)
    grep -rn -E 'event\s*=\s*\{|emit_event\(.*type\s*=' \
        --include="*.py" "${GREP_EXCLUDE_ARGS[@]}" \
        src/armance/service/ 2>/dev/null > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "ad-hoc event dicts in service code (use EventBus.emit instead)"
        show_hits "$tmpfile"
    else
        ok "no ad-hoc event dicts in service code"
    fi

    rm -f "$tmpfile"
}

# ========================================================================
# INVARIANT 6 — JSON-RPC 2.0 envelope
# core/models/rpc.py exists with RpcRequest / RpcResponse / RpcError.
# ========================================================================

check_invariant_6() {
    header "Invariant 6 — JSON-RPC 2.0 envelope"

    if [ -f "src/armance/core/models/rpc.py" ]; then
        if grep -qn "class RpcRequest\|RpcRequest:" src/armance/core/models/rpc.py && \
           grep -qn "class RpcResponse\|RpcResponse:" src/armance/core/models/rpc.py && \
           grep -qn "class RpcError\|RpcError:" src/armance/core/models/rpc.py; then
            ok "core/models/rpc.py declares RpcRequest / RpcResponse / RpcError"
        else
            fail "core/models/rpc.py exists but missing one of RpcRequest / RpcResponse / RpcError"
        fi

        if grep -qn '"2\.0"\|jsonrpc.*=.*"2\.0"' src/armance/core/models/rpc.py; then
            ok "RPC dataclasses use jsonrpc='2.0' field"
        else
            fail "RPC dataclasses do not pin jsonrpc='2.0'"
        fi
    else
        fail "core/models/rpc.py missing"
    fi
}

# ========================================================================
# Legacy hygiene — modules that must be deleted after R-03
# ========================================================================

check_legacy_hygiene() {
    header "Legacy hygiene — post-pivot modules deleted"

    local legacy_modules=(
        "src/armance/service/meeting.py"
        "src/armance/service/judge.py"
        "src/armance/service/task_engine.py"
        "src/armance/service/conversation_manager.py"
        "src/armance/service/migrate.py"
    )

    for m in "${legacy_modules[@]}"; do
        if [ -f "$m" ]; then
            fail "legacy module still present: $m"
        else
            ok "$(basename "$m") deleted"
        fi
    done

    # hr_agent.py must be renamed to recruiter_agent.py
    if [ -f "src/armance/service/agents/hr_agent.py" ]; then
        fail "src/armance/service/agents/hr_agent.py present; rename to recruiter_agent.py"
    else
        ok "hr_agent.py renamed (or absent)"
    fi

    if [ -f "src/armance/service/agents/recruiter_agent.py" ]; then
        ok "recruiter_agent.py present"
    else
        fail "recruiter_agent.py missing"
    fi

    # No imports from legacy
    local tmpfile
    tmpfile=$(mktemp)
    grep -rn -E "from armance\.service\.(meeting|judge|task_engine|conversation_manager|migrate) import" \
        --include="*.py" "${GREP_EXCLUDE_ARGS[@]}" \
        $SCAN_GLOB 2>/dev/null > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "imports from deleted legacy modules"
        show_hits "$tmpfile"
    else
        ok "no imports from legacy modules"
    fi

    rm -f "$tmpfile"
}

check_legacy_paths() {
    header "Legacy paths — fossils removed"

    # No armance.builtin_agents directory
    if [ -d "src/armance/builtin_agents" ]; then
        fail "src/armance/builtin_agents/ still exists"
    else
        ok "src/armance/builtin_agents/ removed"
    fi

    # No talent_creator/workflow_creator helper functions
    if git grep -q "write_default_talent_creator\|write_default_workflow_creator\|TALENT_CREATOR_NAME\|WORKFLOW_CREATOR_NAME" src/armance/ 2>/dev/null; then
        fail "talent_creator / workflow_creator constants or helpers still present"
        git grep -n "write_default_talent_creator\|write_default_workflow_creator\|TALENT_CREATOR_NAME\|WORKFLOW_CREATOR_NAME" src/armance/ | head -5 | sed 's/^/    /'
    else
        ok "talent_creator / workflow_creator helpers removed"
    fi

    # No imports of armance.builtin_agents
    if git grep -q "armance\.builtin_agents\|from armance import builtin_agents" src/armance/ tests/ 2>/dev/null; then
        fail "imports of armance.builtin_agents still present"
    else
        ok "no imports of armance.builtin_agents"
    fi
}

# ========================================================================
# Skill wiring — verify all 11 skills are reachable and imported
# ========================================================================

check_skill_wiring() {
    header "Skill wiring — command-to-skill registrations"

    # Check that HANDLERS dispatchers contain the mapped keys:
    # "agents", "agent", "workflow", "feedback-loop", "iterate-from"
    local handlers_file="src/armance/service/handlers.py"
    if [ ! -f "$handlers_file" ]; then
        fail "$handlers_file missing"
        return
    fi

    local missing=0
    for key in "agents" "agent" "workflow" "feedback-loop" "iterate-from"; do
        if ! grep -q "\"$key\"" "$handlers_file"; then
            fail "HANDLERS dispatcher missing key: $key"
            missing=$((missing + 1))
        fi
    done

    # Check for the expected skill imports/references anywhere in the
    # service/ tree — handlers.py was split into role_ops.py / library_ops.py /
    # save_ops.py and several skills are now imported from those modules.
    local search_paths=(
        "src/armance/service/handlers.py"
        "src/armance/service/role_ops.py"
        "src/armance/service/library_ops.py"
        "src/armance/service/save_ops.py"
        "src/armance/service/skills"
    )
    for skill_cls in "ListAgentsSkill" "EditAgentSkill" "ReplaceAgentSkill" "PromoteAgentSkill" "DemoteAgentSkill" "ArchiveAgentSkill" "DesignWorkflowSkill" "FeedbackLoopSkill" "IterateFromSkill"; do
        if ! grep -rq "$skill_cls" "${search_paths[@]}"; then
            fail "service/ tree does not reference skill class: $skill_cls"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        ok "all slash commands and skill classes are wired in the service tree"
    fi
}

# ========================================================================
# Layer cleanliness — service does not import from client
# ========================================================================

check_layer_cleanliness() {
    header "Layer cleanliness — service does not import from client"

    # Service files must not import from `armance.client` (any submodule)
    local violations
    violations=$(git grep -n "from armance\.client\|import armance\.client" src/armance/service/ 2>/dev/null | grep -v "test_" || true)

    if [ -n "$violations" ]; then
        fail "service imports from client"
        echo "$violations" | head -10 | sed 's/^/    /'
    else
        ok "service has no client imports"
    fi

    # Core must not import from anything besides core
    local core_violations
    core_violations=$(git grep -nE "from armance\.(service|client|transport|providers|storage)" src/armance/core/ 2>/dev/null | grep -v "test_" | grep -v "core.models -> transport.dto" || true)
    # Note: the core.models -> transport.dto exemption is intentional today; leave as a known waiver.

    if [ -n "$core_violations" ]; then
        # Check if these are all the explicitly-allowed exemptions
        local unallowed
        unallowed=$(echo "$core_violations" | grep -v "from armance.transport.dto" || true)
        if [ -n "$unallowed" ]; then
            fail "core imports from outside core (excluding allowed transport.dto exemption)"
            echo "$unallowed" | head -5 | sed 's/^/    /'
        else
            ok "core only imports from core (or transport.dto via exemption)"
        fi
    else
        ok "core only imports from core"
    fi

    # Run lint-imports and check for BROKEN
    if uv run lint-imports --verbose 2>&1 | grep -q "BROKEN"; then
        fail "lint-imports reports BROKEN contracts"
        uv run lint-imports --verbose 2>&1 | grep -B 1 "BROKEN" | sed 's/^/    /'
    else
        ok "lint-imports contracts all KEPT"
    fi
}

# ========================================================================
# INVARIANT 7 — No asyncio.run() in service/ or core/ (FastAPI event-loop
# killer). Allowed in cli.py and scripts/ — those run before any loop.
# ========================================================================

check_invariant_7() {
    header "Invariant 7 — No asyncio.run in service/core"

    local tmpfile
    tmpfile=$(mktemp)
    # Match `asyncio.run(...)` only where the line looks like a real call:
    # an identifier or `await` cannot precede `asyncio.run`, and the line
    # itself isn't a comment / docstring line.
    grep -rn -E '^\s*[^#"]*\basyncio\.run\(' \
        --include="*.py" \
        src/armance/service src/armance/core 2>/dev/null \
        | grep -vE ':\s*#' \
        | grep -vE 'asyncio\.run\(\) (cannot|inside)' \
        > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "asyncio.run() found in service/ or core/ — would crash under FastAPI"
        note "callers live inside a running event loop; use await on the coroutine instead"
        show_hits "$tmpfile"
    else
        ok "no asyncio.run() in service/core"
    fi
    rm -f "$tmpfile"
}

# ========================================================================
# INVARIANT 8 — Dead facade stubs (ArmanceService, transport/local) stay
# removed. dispatch_input is the public service-layer entry.
# ========================================================================

check_invariant_8() {
    header "Invariant 8 — No revival of the dropped facade stubs"

    local tmpfile
    tmpfile=$(mktemp)
    # Exclude the architecture guard test itself — it contains these
    # strings INSIDE a `forbidden = (...)` tuple, by design.
    grep -rn -E '(from armance\.service\.armance_service|from armance\.transport\.local|import armance\.service\.armance_service|import armance\.transport\.local)' \
        --include="*.py" \
        "${GREP_EXCLUDE_ARGS[@]}" \
        --exclude="test_no_dead_facade.py" \
        $SCAN_GLOB 2>/dev/null > "$tmpfile" || true

    if [ -s "$tmpfile" ]; then
        fail "imports of removed ArmanceService / LocalTransport stubs"
        note "use armance.service.tui_bridge.dispatch_input instead"
        show_hits "$tmpfile"
    else
        ok "no imports of the dropped facade stubs"
    fi

    if [ -f "src/armance/service/armance_service.py" ]; then
        fail "src/armance/service/armance_service.py reappeared"
    else
        ok "src/armance/service/armance_service.py absent"
    fi
    if [ -f "src/armance/transport/local.py" ]; then
        fail "src/armance/transport/local.py reappeared"
    else
        ok "src/armance/transport/local.py absent"
    fi
    rm -f "$tmpfile"
}

# ========================================================================
# INVARIANT J.0 — armance.platform scaffold (Epic J, task J.0)
# Package exists; four ABCs + get_current_user exported;
# import-linter contract present.
# ========================================================================

check_invariant_j0() {
    header "Invariant J.0 — armance.platform scaffold"

    local pkg_init="src/armance/platform/__init__.py"

    if [ ! -f "$pkg_init" ]; then
        fail "$pkg_init missing — armance.platform package not scaffolded"
        return
    else
        ok "$pkg_init exists"
    fi

    # Four ABCs must be exported
    for sym in "Storage" "SessionRegistry" "EventBus" "WorkflowExecutor"; do
        if grep -q "\b${sym}\b" "$pkg_init"; then
            ok "$pkg_init exports $sym"
        else
            fail "$pkg_init does not export $sym"
        fi
    done

    # get_current_user must be exported
    if grep -q "get_current_user" "$pkg_init"; then
        ok "$pkg_init exports get_current_user"
    else
        fail "$pkg_init does not export get_current_user"
    fi

    # import-linter contract present
    if grep -q "platform-limits" .importlinter 2>/dev/null; then
        ok "import-linter platform-limits contract present in .importlinter"
    else
        fail "import-linter platform-limits contract missing from .importlinter"
    fi

    # platform must not import service or client (static check)
    local tmpfile
    tmpfile=$(mktemp)
    grep -rn -E '^\s*(from|import)\s+armance\.(service|client)' \
        src/armance/platform/ --include="*.py" 2>/dev/null > "$tmpfile" || true
    if [ -s "$tmpfile" ]; then
        fail "armance.platform imports from armance.service or armance.client"
        show_hits "$tmpfile"
    else
        ok "armance.platform does not import from service or client"
    fi
    rm -f "$tmpfile"
}

# ========================================================================
# Run all checks
# ========================================================================

echo -e "${BOLD}check_invariants.sh — Armance future-web invariants${NC}"
echo "Repo: $REPO_ROOT"
echo "Spec: docs/spec/23_future_web_layer.md"

check_invariant_1
check_invariant_2
check_invariant_3
check_invariant_4
check_invariant_5
check_invariant_6
check_invariant_7
check_invariant_8
check_legacy_hygiene
check_legacy_paths
check_skill_wiring
check_layer_cleanliness
check_invariant_j0

# ========================================================================
# Summary
# ========================================================================

echo ""
echo "========================================"
if [ "$VIOLATIONS" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}ALL CHECKS PASSED${NC} ($INVARIANTS_OK ok)"
    echo "========================================"
    exit 0
else
    echo -e "${RED}${BOLD}FAILED: $VIOLATIONS violation(s)${NC} ($INVARIANTS_OK ok)"
    echo "========================================"
    echo ""
    echo "Read docs/spec/23_future_web_layer.md for the full rationale."
    echo "Fix every violation before committing."
    exit 1
fi
}
