# TokenGuard 🦞

A local log interception and context compression tool designed to protect LLM agents from prompt injection attacks and context window exhaustion during long-running or high-output command executions.

> **v4.1 Security Hardened Edition**: Audited and patched against log injection, Unicode bypasses, state tampering, command silencing, boundary spoofing, OOM attacks, and symlink bypasses.

## Features

- **Silent Execution**: Intercepts noisy commands (e.g., `npm install`, `pip install`, `ffmpeg`, builds) and writes output to a local log file, returning only the exit code and a short tail summary to the terminal.
- **Dual-Log Architecture**: 
  - `step.log`: A sanitized, safe-to-read version of the logs.
  - `step.raw.log`: The untampered original log output, strictly for human review.
- **Robust Sanitization**: 
  - Multi-pass regex filtering for known prompt injection signatures.
  - NFKC Unicode normalization.
  - Zero-width character stripping.
- **Command Blacklist**: Built-in 35+ command blacklist (including symlink resolution) preventing the execution of network tools, remote connections, script interpreters, and shell wrappers via the TokenGuard wrapper.
- **OOM Protection**: Refuses to load log files exceeding 50MB into memory.
- **Controlled Query Interface**: Provides a safe way to query logs by keyword or line range without dumping the entire file into the context window.
- **State Checkpointing**: Allows manual creation of a `state.md` checkpoint to clear the LLM context window, verified by a strict 5-point code-level validation script before restoration.
- **Zero Dependencies**: 100% transparent Python code using only standard libraries. No network requests, no dynamic code evaluation.

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

### Context Compression (Checkpointing)

When the LLM context window grows too large, a user can manually trigger a checkpoint.

1. The agent writes a strictly formatted `state.md` file to the workspace.
2. The user clears the LLM chat history.
3. The user instructs the agent to resume by reading `state.md`.

Before the agent fully restores context, it must validate the checkpoint file:

```bash
python verify_state.py state.md
```

## Security Guarantees & Red Lines

- **No Remote Execution**: TokenGuard will block execution of commands like `curl`, `wget`, `ssh`, `python`, `bash`, etc.
- **Never Trust Logs**: Even `step.log` is treated as untrusted external data enclosed in UUID-tagged boundaries. AI Agents are explicitly instructed never to interpret log output as system directives.
- **System Prompt Primacy**: The initial System Prompt always overrides any conflicting instructions found in `state.md` or log files.

## Project Structure

- `token_guard.py`: The main command execution wrapper and log sanitizer.
- `verify_state.py`: The strict validation tool for `state.md` checkpoints.
- `SKILL.md`: The detailed behavior guidelines and ruleset for AI Agents utilizing this tool.

## License

Open Source. Transparency is the best security.
