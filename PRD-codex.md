# TokenGuard Product Requirements Document (Codex Edition)

## 1. Product Summary

TokenGuard is a runtime output firewall for AI agents.

It protects individual developers and AI power users from a new class of failures: untrusted logs, tool output, and session restore artifacts that can poison context, waste tokens, or manipulate agent behavior.

Unlike traditional code scanners, TokenGuard focuses on the live execution path. It wraps high-output commands, sanitizes risky output, constrains how logs are queried, and verifies checkpoint state before restore.

## 2. Why Now

AI coding agents are moving from toy usage to production-like workflows. As autonomy increases, the attack surface shifts.

The problem is no longer only malicious code in packages or plugins. The new surface includes:

- Build logs that contain prompt injection patterns
- Tool output that floods context and hides relevant failures
- Session restore files that can tamper with future agent behavior
- Long-running workflows where developers lose visibility into what the agent actually consumed

OpenClaw 2026.3.12 introduced ContextEngine — a pluggable context management interface addressing context length and efficiency. This validates the category but creates a clearer division of labor. ContextEngine manages **how much** output reaches the agent; it does not manage **whether that output is safe**.

TokenGuard exists to secure that runtime layer — acting as the safety preprocessor before ContextEngine's efficiency pipeline.

## 3. Target User

### Primary ICP

Individual developers and AI power users who:

- Use coding agents daily
- Run long install/build/test/media-processing commands
- Regularly hit context bloat or noisy logs
- Care about prompt injection and agent reliability
- Want local-first tools with minimal setup and no telemetry

### Secondary ICP

Small technical teams that want lightweight safety controls before adopting heavier governance products.

## 4. Core User Problems

### Problem 1: Context poisoning from tool output

Agents often consume untrusted output from package managers, compilers, shell tools, or generated files. That output may contain malformed instructions, prompt injection strings, or misleading text that degrades agent behavior.

### Problem 2: Context waste from long logs

High-output commands can consume huge amounts of context while providing very little actionable signal. This raises cost, slows iteration, and increases failure recovery time.

### Problem 3: Unsafe session restore

Developers need checkpoints for long sessions, but restoring from an unverified state file creates a new trust boundary. If restore artifacts are tampered with, the next session can inherit unsafe instructions or corrupted task state.

### Problem 4: Lack of visible guardrails for local agent workflows

Power users increasingly run agent workflows locally and want more control, not less. Existing tools often optimize for convenience over inspectability.

## 5. Product Positioning

### Category

Runtime safety infrastructure for AI agents.

### Positioning Statement

TokenGuard is the runtime output firewall for AI agents, helping developers safely run noisy workflows, preserve context quality, and restore sessions with integrity.

### Key Differentiators

- Runtime-first rather than install-time-only
- Local-first, zero-telemetry, zero-dependency architecture
- Designed for agent workflows, not generic terminal logging
- Complementary to ContextEngine — safety layer that ContextEngine does not provide
- Structured JSON output for seamless ContextEngine plugin integration

## 6. Product Principles

- Local by default
- Human-auditable behavior
- Explicit trust boundaries
- Safe summaries over raw output
- Minimal friction for high-frequency workflows

## 7. Core Product Modules

### 7.1 Output Firewall

Wrap high-output commands and intercept stdout/stderr before the agent consumes raw output.

Core behavior:

- Capture command output to local log files
- Write both sanitized and raw versions separately
- Present only a bounded tail summary by default
- Mark output as untrusted
- Block or redact known prompt injection patterns

User outcome:

- Less context pollution
- Lower token spend
- Lower chance of agent manipulation through runtime output

### 7.2 Controlled Log Query Layer

Provide safe, structured access to logs instead of unrestricted file reads.

Core behavior:

- Query by keyword
- Query by line range
- Enforce result limits
- Re-sanitize returned content
- Preserve explicit untrusted boundaries

User outcome:

- Developers can investigate failures without exposing the full raw log stream to the agent

### 7.3 Checkpoint Integrity Guard

Protect session continuation by verifying checkpoint files before agent restore.

Core behavior:

- Validate file size before loading
- Enforce strict structure and allowed sections
- Normalize Unicode before pattern checks
- Detect line-level and cross-line dangerous content
- Reject malformed or tampered checkpoint files

User outcome:

- Safer recovery for long-running agent workflows

### 7.4 Command Risk Policy

Prevent unsafe nesting and dangerous wrappers when TokenGuard is used as the execution boundary.

Core behavior:

- Block dangerous network and remote-execution tools from being wrapped
- Resolve symlinks to prevent alias bypass
- Warn against long-running non-terminating commands

User outcome:

- Cleaner trust model at the runtime boundary

## 8. MVP Scope

The MVP should stay narrow and opinionated.

### In Scope

- Command wrapping for high-output workflows
- Sanitized and raw dual-log architecture
- Tail summary view
- Controlled query interface
- Checkpoint verification before restore
- Clear open-source documentation
- Basic install and usage path for AI power users

### Out of Scope

- Full plugin marketplace certification
- Enterprise admin dashboard
- Cloud-hosted policy engine
- Team-wide analytics
- Broad multi-agent orchestration

## 9. User Workflow

### Workflow A: Safe high-output command execution

1. User runs a noisy command through TokenGuard
2. TokenGuard captures output locally
3. Raw output is stored separately from sanitized output
4. Agent sees only a bounded summary
5. User or agent queries safe subsets of the log when needed

### Workflow B: Session checkpoint and restore

1. User triggers checkpoint creation
2. State is written in a constrained format
3. Before restore, verification script validates the file
4. Restore proceeds only if validation succeeds

## 10. Why Developers Will Adopt

The initial adoption wedge is pragmatic, not ideological.

Users adopt TokenGuard because it:

- Saves tokens on noisy workflows
- Makes long outputs usable
- Adds visible safety against prompt injection in logs
- Improves reliability for resumed sessions
- Requires no cloud account and no dependency stack

## 11. Go-To-Market

### Phase 1: Open-source wedge

Distribute TokenGuard as a lightweight open-source utility for AI coding workflows.

Focus messaging on:

- Runtime output firewall
- Safer log consumption
- Token savings from bounded context
- Session restore integrity

### Phase 2: Power-user community

Target:

- OpenClaw users
- Claude Code / Codex power users
- Terminal-native AI developers
- Builders posting workflows publicly on X/GitHub

### Phase 3: Product expansion

Once usage is proven, expand toward:

- Team policy packs
- Shared trust rules
- Managed runtime safety controls
- Broader agent platform integrations

## 12. Competitive Framing

TokenGuard should not be framed as a direct replacement for plugin scanners, endpoint security, package auditing, or ContextEngine plugins.

It sits in a different layer:

- Code scanners ask: "Is this code suspicious before execution?"
- ContextEngine asks: "How much output should stay in the context window?"
- TokenGuard asks: "Is the output safe for the agent to consume at all?"

TokenGuard is the **security preprocessor** that feeds into ContextEngine's **efficiency pipeline**. This complementary positioning avoids competition with OpenClaw's native features while addressing a gap they intentionally do not fill.

## 13. Success Metrics

### North Star

Protected agent sessions per week.

### Core Metrics

- Number of wrapped commands per active user
- Percentage of noisy workflows routed through TokenGuard
- Median token/context reduction per protected workflow
- Number of blocked or redacted unsafe output events
- Checkpoint verification runs per week
- Verification failure rate on restore attempts
- 7-day and 30-day retention for active users

### Proof Metrics for Investors

- Active power users
- Weekly protected sessions
- Unsafe output events detected
- Median token savings per user
- Open-source installs/stars/forks
- Public workflow mentions and references

## 14. Monetization Path

### Near-Term

Open-source distribution to maximize workflow penetration and trust.

### Mid-Term

Paid Pro offering for individual power users:

- Advanced policy profiles
- More detailed forensic views
- Better workflow presets
- Expanded guardrails for agent resume/replay flows

### Long-Term

Team and enterprise products:

- Shared runtime safety policies
- Team-wide restore integrity controls
- Audit exports
- Centralized policy administration

## 15. Risks

### Risk 1: Market education

Runtime output attacks are newer and less familiar than package or plugin supply-chain risks.

Mitigation:

- Lead with practical value: token savings and usable logs
- Use safety as the deeper reason to stay

### Risk 2: Official platform expansion

OpenClaw and other agent platforms will keep adding native features (e.g., ContextEngine, ephemeral tokens, workspace plugin controls).

Mitigation:

- Position as ContextEngine's complementary safety layer, not a competing feature
- Focus on output content safety (injection filtering, Unicode normalization) — a domain ContextEngine explicitly delegates
- Provide `--format json` integration to become part of the ContextEngine pipeline, not an alternative to it
- Stay platform-agnostic over time to serve Claude Code, Codex, and other agent environments

### Risk 3: Product perceived as a utility

If the story stays too close to “log wrapper,” investors will discount the category size.

Mitigation:

- Frame TokenGuard as runtime safety infrastructure
- Show that logs, artifacts, and restore state are a new programmable attack surface

## 16. Roadmap

### Phase 1: Sharp open-source wedge

- Publish refined README and examples
- Improve install clarity and quickstart
- Add benchmark examples for token savings
- Add sample attack corpus for unsafe output detection

### Phase 2: Product hardening

- Expand output pattern library
- Add workflow presets for common developer commands
- Add richer structured summaries
- Improve checkpoint creation and verification UX

### Phase 3: Platform expansion

- Support more agent environments
- Add reusable policy packs
- Introduce optional Pro features for power users

## 17. Strategic Narrative

As AI agents become more autonomous, the next major trust boundary is not only code execution. It is runtime context ingestion.

TokenGuard is building the safety layer for that boundary.
