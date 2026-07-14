"""Run one Claude Code headless turn (`claude -p`) and parse the result.

Every LLM role in the harness (User, Inner, Validator, Outer, Importer) is a
subprocess of this shape. The binary is overridable via PIPELINE_CLAUDE_BIN so
tests can substitute a scripted stub and the whole harness runs offline.

Multi-turn sessions (the Inner run) work by capturing `session_id` from the
first turn and passing it back as `resume` on later turns.
"""
import json
import os
import re
import subprocess


class ClaudeError(Exception):
    pass


class ClaudeResult:
    def __init__(self, text, session_id, cost_usd, events, ok, error=None):
        self.text = text                # final assistant text ("result" field)
        self.session_id = session_id
        self.cost_usd = cost_usd or 0.0
        self.events = events            # stream-json events (empty for plain json output)
        self.ok = ok
        self.error = error

    def json_payload(self):
        """Extract a strict-JSON payload from the assistant text.

        Roles that must answer in JSON sometimes wrap it in prose or a code
        fence; take the outermost object.
        """
        text = self.text or ""
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return json.loads(fenced.group(1))
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ClaudeError(f"no JSON object in response: {text[:300]!r}")
        return json.loads(text[start:end + 1])


def claude_bin():
    return os.environ.get("PIPELINE_CLAUDE_BIN", "claude")


def run_claude(prompt, *, model, cwd, timeout_s,
               system_prompt=None, append_system_prompt=None,
               allowed_tools=None, disallowed_tools=None, add_dirs=None,
               resume=None, env_extra=None, transcript_path=None,
               settings=None, strict_mcp=False):
    """One headless turn. Returns ClaudeResult; raises ClaudeError on hard failure.

    transcript_path: when set, uses --output-format stream-json and writes the
    raw event stream there (this is how live runs get recorded — the recorder
    parses Exa traffic out of the transcript's tool calls as a fallback to the
    env shims).
    """
    stream = transcript_path is not None
    cmd = [claude_bin(), "-p", "--model", model,
           "--permission-mode", "bypassPermissions",
           "--output-format", "stream-json" if stream else "json"]
    if stream:
        cmd.append("--verbose")
    if strict_mcp:
        # No inherited MCP servers: an Exa MCP tool would bypass the
        # curl/urllib shims, defeating recording (live) and hermeticity (replay)
        cmd.append("--strict-mcp-config")
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    if append_system_prompt:
        cmd += ["--append-system-prompt", append_system_prompt]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if disallowed_tools:
        cmd += ["--disallowedTools", ",".join(disallowed_tools)]
    for d in (add_dirs or []):
        cmd += ["--add-dir", d]
    if resume:
        cmd += ["--resume", resume]
    if settings:
        cmd += ["--settings", json.dumps(settings)]
    cmd.append(prompt)

    env = dict(os.environ)
    # A None value means "unset this var for the subprocess" (used to route an
    # actor at a non-default provider without an ambient key shadowing it).
    for k, v in (env_extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v

    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return ClaudeResult("", None, 0.0, [], ok=False,
                            error=f"timed out after {timeout_s}s")
    except OSError as e:  # missing binary, E2BIG on an oversized prompt, ...
        return ClaudeResult("", None, 0.0, [], ok=False,
                            error=f"failed to exec {cmd[0]}: {e}")

    if stream:
        events = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if transcript_path:
            with open(transcript_path, "w") as f:
                f.write(proc.stdout)
        final = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if final is None:
            return ClaudeResult("", None, 0.0, events, ok=False,
                                error=f"no result event (exit {proc.returncode}): "
                                      f"{proc.stderr[:500]}")
        return ClaudeResult(final.get("result") or "", final.get("session_id"),
                            final.get("total_cost_usd"), events,
                            ok=not final.get("is_error", False),
                            error=final.get("result") if final.get("is_error") else None)

    # plain json output
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ClaudeResult("", None, 0.0, [], ok=False,
                            error=f"unparseable output (exit {proc.returncode}): "
                                  f"{proc.stdout[:300]!r} stderr={proc.stderr[:300]!r}")
    return ClaudeResult(payload.get("result") or "", payload.get("session_id"),
                        payload.get("total_cost_usd"), [],
                        ok=not payload.get("is_error", False),
                        error=payload.get("result") if payload.get("is_error") else None)
