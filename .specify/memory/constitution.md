<!--
  ============================================================================
  Sync Impact Report
  ============================================================================
  Version change: 1.0.0 → 1.1.0 (MINOR: new Hardware Constraints section)
  Modified principles: none
  Added sections:
    - Hardware Constraints (USB-only, no WiFi/Bluetooth)
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md         ✅ no changes needed
    - .specify/templates/spec-template.md         ✅ no changes needed
    - .specify/templates/tasks-template.md        ✅ no changes needed
    - .specify/templates/checklist-template.md    ✅ no changes needed
    - .opencode/commands/*.md                     ✅ no changes needed
  Follow-up TODOs: none
  ============================================================================
-->

# OpenCode Light Constitution

## Core Principles

### I. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before any implementation begins:

- State assumptions explicitly. If uncertain, MUST ask for clarification.
- If multiple interpretations exist, MUST present them rather than silently choosing one.
- If a simpler approach exists, MUST propose it. Push back on unnecessary complexity.
- If something is unclear, MUST stop and name what is confusing before proceeding.

Rationale: Errors compound when assumptions go unstated. Surfacing ambiguity
early prevents rework and produces better designs.

### II. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

Every change MUST satisfy:

- No features beyond what was explicitly requested.
- No abstractions created for single-use code paths.
- No "flexibility" or "configurability" that was not requested.
- No error handling for impossible scenarios.
- If a solution exceeds a reasonable size for its purpose, it MUST be rewritten
  to the minimal implementation.

Self-test: "Would a senior engineer say this is overcomplicated?" If yes,
simplify before submitting.

Rationale: Speculative code is dead weight. It complicates understanding, testing,
and maintenance. Every line must earn its existence.

### III. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- MUST NOT "improve" adjacent code, comments, or formatting not related to
  the change.
- MUST NOT refactor code that is not broken by the change.
- MUST match existing style even when the agent prefers a different approach.
- If unrelated dead code is noticed, MUST mention it but MUST NOT delete it.

When a change creates orphans:
- MUST remove imports, variables, and functions made unused by the change.
- MUST NOT remove pre-existing dead code unless explicitly asked.

The test: Every changed line MUST trace directly to the user's request.

Rationale: Defocused diffs hide bugs, complicate review, and risk regressions.
Changes must be auditable by their scope.

### IV. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Every task MUST be transformed into verifiable goals:

| Task Type | Goal Transformation |
|-----------|-------------------|
| "Add validation" | Write tests for invalid inputs, then make them pass |
| "Fix the bug" | Write a test that reproduces it, then make it pass |
| "Refactor X" | Ensure all existing tests pass before and after |

For multi-step tasks, MUST state a brief plan with explicit verification per step:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria enable autonomous iteration. Weak criteria ("make it
work") require constant clarification and MUST be avoided.

Rationale: Without explicit success criteria, work drifts. Verifiable goals
create a tight feedback loop that prevents both over-engineering and under-delivery.

## Agent-Specific Constraints

These constraints apply specifically to OpenCode AI agent development within
this project:

1. **Delegation First**: The orchestrator agent MUST decompose work and delegate
   to specialized subagents rather than implementing directly. Direct
   implementation is only acceptable for trivial single-file changes.

2. **Parallel by Default**: Independent work units MUST be executed in parallel.
   Sequential execution of independent tasks is an anti-pattern.

3. **Todo Accountability**: Multi-step tasks MUST create a tracked todo list
   before starting. Each item MUST encode WHERE, HOW, WHY, and EXPECTED RESULT
   in the title. One item in-progress at a time.

4. **LSP Validation**: After every file change, LSP diagnostics MUST be checked.
   Type errors MUST NEVER be suppressed with `as any`, `@ts-ignore`, or
   equivalent escape hatches.

5. **Evidence Required**: A task is not complete without evidence: clean
   diagnostics, passing build (if applicable), and passing tests (if
   applicable).

## Hardware Constraints

These constraints govern all ESP32 hardware interaction within this project:

1. **USB-Only Communication**: All communication with the ESP32 development board
   MUST occur exclusively via USB wired (serial) connection.

2. **WiFi Prohibited**: WiFi functionality on the ESP32 MUST NOT be enabled,
   configured, or used. No WiFi initialization code, no SSID scanning, no
   network connections over WiFi.

3. **Bluetooth Prohibited**: Bluetooth (Classic and BLE) functionality on the
   ESP32 MUST NOT be enabled, configured, or used. No Bluetooth stack
   initialization, no advertising, no pairing, no GATT operations.

4. **Build Verification**: Firmware builds MUST be verified to exclude WiFi and
   Bluetooth compilation units. Any accidental inclusion of wireless modules in
   build output is a compliance violation.

5. **Tool Selection**: All ESP32 tooling, flashing, monitoring, and testing MUST
   operate over serial port (UART/USB). Network-based OTA updates, mDNS
   discovery, and WiFi-based debugging are prohibited.

Rationale: This project operates in an environment where wireless communication
is restricted. USB serial provides the necessary debugging, flashing, and
monitoring capabilities without introducing wireless attack surface or
regulatory concerns.

## Quality Gates

Before any implementation can be considered complete, the following gates
MUST pass:

1. **Constitution Compliance**: All four core principles verified against
   the diff. Any violation MUST be justified in writing.

2. **Surgical Scope**: Every changed line traces to the request. No
   opportunistic refactoring, no "while I was here" improvements.

3. **Simplicity Audit**: The solution is the minimum code necessary. No
   speculative abstractions, no future-proofing, no dead error handlers.

4. **Verification Evidence**: Build passes, tests pass, LSP diagnostics
   clean on all changed files.

5. **Self-Review**: After significant implementation, the agent MUST consult
   Oracle for code quality review before declaring completion.

## Governance

This constitution supersedes all other development practices within the
OpenCode Light project. It defines non-negotiable principles that all
agents and subagents MUST follow.

**Amendment Process**:
- Amendments MUST be proposed via documented rationale.
- Amendments that remove or redefine principles require a MAJOR version bump.
- New principles or materially expanded guidance require a MINOR version bump.
- Clarifications and wording fixes require a PATCH version bump.

**Compliance Review**:
- Every plan.md MUST include a Constitution Check section verified against
  all active principles.
- Every implementation MUST pass Quality Gates before completion.
- Complexity that violates Simplicity First MUST be explicitly justified
  in the plan's Complexity Tracking table.

**Runtime Guidance**: See AGENTS.md for session-level agent instructions that
operationalize these principles.

**Version**: 1.1.0 | **Ratified**: 2026-05-31 | **Last Amended**: 2026-05-31
