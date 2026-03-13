# TokenGuard 🦞

A runtime output firewall for AI agents — sanitizes tool output before it reaches the agent's context, protecting against prompt injection, context poisoning, and unsafe session restoration.

> **v5.0 — ContextEngine Complement Edition**: Repositioned as the security preprocessor for OpenClaw's ContextEngine. TokenGuard handles **output safety** (injection filtering, Unicode normalization, zero-width stripping); ContextEngine handles **context efficiency** (compression, summarization, window management).

## How It Fits with OpenClaw ContextEngine

```
Command Output → [TokenGuard: safety filtering] → [ContextEngine: context management] → Agent
```

TokenGuard and ContextEngine solve **different problems**:
- **TokenGuard** asks: *"Is this output safe for the agent to consume?"*
- **ContextEngine** asks: *"How much of this output should stay in the context window?"*

Use them together for defense-in-depth.

## Features

- **Runtime Output Sanitization** (TokenGuard's unique value):
  - Multi-pass regex filtering for 15+ known prompt injection signatures
  - NFKC Unicode normalization to defeat homoglyph attacks
  - Zero-width character stripping to prevent invisible injection
  - UUID-tagged untrusted output boundaries

- **Dual-Log Architecture**: 
  - `step.log`: A sanitized, safe-to-read version of the logs
  - `step.raw.log`: The untampered original log output, strictly for human review

- **Structured JSON Output** (`--format json`):
  - Machine-readable output for ContextEngine plugin `ingest` hooks
  - Includes exit code, line counts, sanitization stats, and tail summary

- **Command Blacklist**: 35+ command blacklist (including symlink resolution) preventing execution of network tools, remote connections, script interpreters, and shell wrappers via TokenGuard

- **OOM Protection**: Refuses to load log files exceeding 50MB into memory

- **Controlled Query Interface**: Safe log querying by keyword or line range with result limits and re-sanitization

- **Checkpoint Integrity Guard** (legacy compatibility):
  - Validates `state.md` checkpoint files with 5-point code-level verification
  - For new setups, consider using ContextEngine plugins for context management

- **Zero Dependencies**: 100% transparent Python code using only standard libraries. No network requests, no dynamic code evaluation, no telemetry.

## Installation

TokenGuard consists of two standalone Python scripts. Simply clone the repository or download the scripts to your AI workspace.

```bash
git clone https://github.com/manxc/token_guard.git
cd token_guard
```

## Usage

### Command Execution

Wrap any long-output command with `token_guard.py`:

```bash
python token_guard.py npm install
python token_guard.py pip install -r requirements.txt
python token_guard.py docker build .
```

*Note: Do not use TokenGuard for long-running daemon services (like `npm run dev` or `docker-compose up` without `-d`), as it will wait indefinitely for the process to exit.*

### Structured JSON Output (for ContextEngine)

Use `--format json` to get machine-readable output:

```bash
python token_guard.py --format json npm install
```

Output:
```json
{
  "tokenguard_version": "5.0",
  "command": "npm install",
  "exit_code": 0,
  "total_lines": 1523,
  "sanitized_lines": 3,
  "tail_lines": ["...last 30 lines..."],
  "log_file": "/path/to/.claw_logs/step.log",
  "raw_log_file": "/path/to/.claw_logs/step.raw.log"
}
```

### Log Inspection

TokenGuard provides a controlled `--query` interface to safely search the sanitized `step.log`.

```bash
# Get line count and summary
python token_guard.py --query

# Search for a keyword
python token_guard.py --query error
python token_guard.py --query "ENOENT"

# View a specific line range (max 100 lines per query)
python token_guard.py --query 10-50
```

### Context Compression (Legacy Checkpointing)

> For new setups using OpenClaw 2026.3.12+, consider using ContextEngine plugins for automated context management instead.

When the LLM context window grows too large, a user can manually trigger a checkpoint:

1. The agent writes a strictly formatted `state.md` file to the workspace
2. The user clears the LLM chat history
3. The user instructs the agent to resume by reading `state.md`

Before the agent restores context, it must validate the checkpoint file:

```bash
python verify_state.py state.md
```

## Security Guarantees & Red Lines

- **Output Sanitization**: 15+ regex patterns covering English/Chinese prompt injection, dangerous commands, LLM special tokens — all applied after NFKC Unicode normalization
- **No Remote Execution**: TokenGuard blocks execution of commands like `curl`, `wget`, `ssh`, `python`, `bash`, etc.
- **Never Trust Logs**: Even `step.log` is treated as untrusted external data enclosed in UUID-tagged boundaries
- **System Prompt Primacy**: The initial System Prompt always overrides any conflicting instructions found in `state.md` or log files

## Project Structure

- `token_guard.py`: Runtime output firewall — command wrapper, log sanitizer, JSON output
- `verify_state.py`: Checkpoint validator for `state.md` (legacy compatibility)
- `SKILL.md`: Agent behavior guidelines and runtime output firewall rules

## License

Open Source. Transparency is the best security.
