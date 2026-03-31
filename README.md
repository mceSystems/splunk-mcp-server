# splunk-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Splunk Enterprise to AI assistants (Claude Desktop, Cursor, and any other MCP client).

Ask Claude things like:
- *"Search Splunk for authentication failures in the last hour"*
- *"Why can't user jsmith see the Security dashboard?"*
- *"What indexes are available and how much data is in each?"*
- *"List all fired alerts from the last 24 hours"*
- *"Show me the definition of the `normalize_src_ip` macro"*

## Tools (26 total)

| Category | Tools |
|---|---|
| **Search** | `splunk_search`, `splunk_search_export`, `splunk_get_job_status`, `splunk_get_job_results` |
| **Saved searches** | `splunk_list_saved_searches`, `splunk_get_saved_search`, `splunk_run_saved_search` |
| **Indexes** | `splunk_list_indexes`, `splunk_get_index_info` |
| **Dashboards** | `splunk_list_dashboards`, `splunk_get_dashboard` |
| **Macros** | `splunk_list_macros`, `splunk_get_macro` |
| **Users** | `splunk_list_users`, `splunk_get_user` |
| **Roles** | `splunk_list_roles`, `splunk_get_role` |
| **Permissions** | `splunk_get_object_acl`, `splunk_check_user_permissions`, `splunk_diagnose_access`, `splunk_list_app_permissions` |
| **Alerts** | `splunk_list_fired_alerts` |
| **Apps** | `splunk_list_apps` |
| **KV Store** | `splunk_list_kvstore_collections`, `splunk_query_kvstore` |
| **System** | `splunk_get_server_info` |

---

## Prerequisites

- Splunk Enterprise 8.x or 9.x
- A Splunk **Bearer token** (Settings → Tokens, or via `splunk create-authtokens`)
- Python 3.10+ **or** Docker

---

## Installation

### Option A — pip (recommended for most users)

```bash
pip install splunk-mcp
```

### Option B — uvx (no permanent install, always latest)

```bash
# No install step needed — uvx fetches and runs on demand
uvx splunk-mcp
```

[Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

### Option C — from source

```bash
git clone https://github.com/mceSystems/splunk-mcp-server
cd splunk-mcp
pip install -e .
```

### Option D — Docker

```bash
docker build -t splunk-mcp .
```

---

## Configuration

All settings are read from environment variables or a `.env` file in the working directory.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SPLUNK_HOST` | yes | — | Hostname or IP of your Splunk instance |
| `SPLUNK_TOKEN` | yes | — | Bearer token for authentication |
| `SPLUNK_PORT` | no | `8089` | Management API port |
| `SPLUNK_VERIFY_SSL` | no | `true` | Set `false` for self-signed certificates |
| `SPLUNK_TIMEOUT` | no | `30.0` | HTTP request timeout in seconds |
| `SPLUNK_MAX_WAIT` | no | `120.0` | Maximum time to wait for a search job |
| `SPLUNK_MAX_RESULTS` | no | `100` | Default result cap for searches |

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

---

## Claude Desktop setup

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

### pip install

```json
{
  "mcpServers": {
    "splunk": {
      "command": "splunk-mcp",
      "env": {
        "SPLUNK_HOST": "your-splunk-host",
        "SPLUNK_TOKEN": "your-bearer-token",
        "SPLUNK_PORT": "8089",
        "SPLUNK_VERIFY_SSL": "false"
      }
    }
  }
}
```

### uvx (recommended — always runs the latest published version)

```json
{
  "mcpServers": {
    "splunk": {
      "command": "uvx",
      "args": ["splunk-mcp"],
      "env": {
        "SPLUNK_HOST": "your-splunk-host",
        "SPLUNK_TOKEN": "your-bearer-token",
        "SPLUNK_PORT": "8089",
        "SPLUNK_VERIFY_SSL": "false"
      }
    }
  }
}
```

### From source / editable install

```json
{
  "mcpServers": {
    "splunk": {
      "command": "python",
      "args": ["-m", "splunk_mcp.server"],
      "cwd": "C:\\dev\\splunk-mcp",
      "env": {
        "SPLUNK_HOST": "your-splunk-host",
        "SPLUNK_TOKEN": "your-bearer-token",
        "SPLUNK_PORT": "8089",
        "SPLUNK_VERIFY_SSL": "false"
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "splunk": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SPLUNK_HOST=your-splunk-host",
        "-e", "SPLUNK_TOKEN=your-bearer-token",
        "-e", "SPLUNK_PORT=8089",
        "-e", "SPLUNK_VERIFY_SSL=false",
        "splunk-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop after editing the config.

---

## Cursor setup

Edit `~/.cursor/mcp.json` (create it if it doesn't exist). Use the same JSON block as above — Cursor uses the identical MCP config format.

---

## Verifying the connection

After restarting your MCP client, ask:

> "Get Splunk server info"

Claude should respond with your Splunk version, build number, and license type. If it returns an error, check:

1. `SPLUNK_HOST` is reachable from your machine on port `SPLUNK_PORT`
2. The bearer token is valid and not expired
3. `SPLUNK_VERIFY_SSL=false` if using a self-signed certificate

---

## Example prompts

### Search

```
Search Splunk for failed logins in the last 4 hours
```
```
Run this SPL: index=web_logs status=500 | stats count by host | sort -count
```
```
Search for errors in index=main over the last 7 days, limit to 50 results
```

### Indexes & data

```
What Splunk indexes do I have and how much data is in each?
```
```
Show me the retention policy for the security index
```

### Saved searches & reports

```
List all saved searches in the "search" app
```
```
Run the saved search named "Daily Error Summary"
```

### Dashboards

```
List all dashboards in the SplunkEnterpriseSecuritySuite app
```
```
Show me the XML for the "Executive Summary" dashboard
```

### Macros

```
List all search macros that contain "lookup" in the name
```
```
What does the macro `cim_authentication_indexes` expand to?
```

### Users & roles

```
List all Splunk users and their roles
```
```
What capabilities does the "power" role have?
```
```
Show me everything the user jsmith is allowed to do
```

### Permission troubleshooting

```
Why can't jsmith see the "Security Overview" dashboard in the search app?
```
```
Check if analyst_user has read access to the saved search "Weekly Threat Report"
```
```
Which apps are globally shared vs private?
```
```
Show the ACL for the macro `normalize_src_ip` in the Splunk_SA_CIM app
```

### KV Store

```
List KV Store collections in the "lookup_editor" app
```
```
Query the "asset_lookup" KV Store collection for records where type is "server"
```

---

## Publishing to PyPI

```bash
pip install build twine

# Build source dist + wheel
python -m build

# Upload (needs a PyPI account and API token)
twine upload dist/*
```

Set your name and email in `pyproject.toml` before publishing.

---

## Security notes

- The bearer token is passed via environment variable, not embedded in config files checked into source control
- Add `.env` to `.gitignore` — never commit credentials
- Use `SPLUNK_VERIFY_SSL=true` in production; `false` is only for dev/internal instances with self-signed certs
- The server only makes read requests (GET) plus search job creation/deletion — it does not modify Splunk configuration

---

## License

MIT
