# Splunk MCP — Workflow Guide

Use this guide to work effectively with the 23 tools in this server.

---

## Tool Inventory

### Search
| Tool | Purpose |
|------|---------|
| `splunk_search` | Run SPL query, block until done, return up to `max_results` rows |
| `splunk_search_export` | Streaming export endpoint — better for large result sets (default max 1000) |
| `splunk_get_job_status` | Poll a running search job by SID |
| `splunk_get_job_results` | Fetch paginated results from a completed job by SID |

### Indexes
| Tool | Purpose |
|------|---------|
| `splunk_list_indexes` | List indexes visible to this token (uses SPL — only indexes with recent events appear) |
| `splunk_get_index_info` | Detailed config for one index: size, retention, home/cold path |

### Apps
| Tool | Purpose |
|------|---------|
| `splunk_list_apps` | List installed Splunk apps |

### Saved Searches & Alerts
| Tool | Purpose |
|------|---------|
| `splunk_list_saved_searches` | List saved search definitions and their schedules |
| `splunk_get_saved_search` | Full config for one saved search (SPL, schedule, alert actions) |
| `splunk_run_saved_search` | Dispatch a saved search and return its SID |
| `splunk_list_fired_alerts` | Recently triggered alert instances |

### Dashboards
| Tool | Purpose |
|------|---------|
| `splunk_list_dashboards` | List dashboards (optionally scoped to an app) |
| `splunk_get_dashboard` | Fetch the raw XML definition of a dashboard |

### KV Store
| Tool | Purpose |
|------|---------|
| `splunk_list_kvstore_collections` | List KV store collections and their field schema |
| `splunk_query_kvstore` | Query a collection with a MongoDB-style filter |

### Macros
| Tool | Purpose |
|------|---------|
| `splunk_list_macros` | List SPL macros |
| `splunk_get_macro` | Full definition of one macro (definition string, arguments) |

### Users & Roles
| Tool | Purpose |
|------|---------|
| `splunk_list_users` | List Splunk users |
| `splunk_get_user` | Details and capabilities for one user |
| `splunk_list_roles` | List roles with search quotas |
| `splunk_get_role` | Full capability set for one role |

### Permissions
| Tool | Purpose |
|------|---------|
| `splunk_get_object_acl` | ACL, owner, sharing, and read/write roles for any Splunk object |

### Server
| Tool | Purpose |
|------|---------|
| `splunk_get_server_info` | Splunk version, build, license type |

---

## Common Workflows

### 1. Orient yourself in a new Splunk environment

```
splunk_get_server_info()          # version, license
splunk_list_indexes(count=50)     # what data exists
splunk_list_apps()                # which apps are installed
splunk_list_saved_searches()      # existing search library
```

### 2. Investigate a data source

```
# Confirm the index exists and has recent data
splunk_list_indexes(time_window="-24h")

# Sample raw events
splunk_search('index=<name> | head 20')

# Understand field coverage
splunk_search('index=<name> | fieldsummary maxvals=5 | table field count distinct_count')
```

### 3. Audit access controls

```
splunk_list_users()
splunk_get_user(username="alice")
splunk_list_roles()
splunk_get_role(name="power")
splunk_get_object_acl(object_type="saved/searches", name="my_search", app="search")
```

### 4. Work with saved searches and alerts

```
splunk_list_saved_searches(app="search")
splunk_get_saved_search(name="Error Rate", app="search")   # see exact SPL + schedule
splunk_run_saved_search(name="Error Rate", app="search")   # returns SID
splunk_get_job_status(sid="<sid>")
splunk_get_job_results(sid="<sid>", count=200)
```

### 5. Long-running or large searches

```
# Option A: export endpoint handles large volumes better
splunk_search_export('index=main error', earliest_time='-7d', max_results=5000)

# Option B: manual job polling (for very long searches)
splunk_search('index=main | rare host')                    # blocks up to SPLUNK_MAX_WAIT
# If it times out, you get the SID back — then:
splunk_get_job_status(sid="<sid>")                         # wait for dispatchState=DONE
splunk_get_job_results(sid="<sid>", count=500, offset=0)  # paginate as needed
```

---

## Tool Selection Guide

| Scenario | Use |
|----------|-----|
| Quick ad-hoc query, ≤100 rows | `splunk_search` |
| Exporting thousands of rows | `splunk_search_export` |
| Search you know will run >2 min | `splunk_search` → save SID → poll `splunk_get_job_status` → fetch with `splunk_get_job_results` |
| Run a pre-built search | `splunk_run_saved_search` → poll → `splunk_get_job_results` |
| Investigate why someone can't see data | `splunk_get_user` + `splunk_get_role` + `splunk_get_object_acl` |
| Understand dashboard logic | `splunk_get_dashboard` (returns XML with embedded SPL panels) |
| Enrich search with lookup table | `splunk_list_kvstore_collections` + `splunk_query_kvstore` |

---

## Gotchas

- **`splunk_list_indexes` uses SPL** — it queries `| tstats count where index=* groupby index`.
  Indexes that had zero events in `time_window` (default `-7d`) won't appear.
  Use a wider window (`time_window="-30d"`) or `splunk_get_index_info` for a specific known index.

- **`splunk_search` blocks** until the job completes or `SPLUNK_MAX_WAIT` (default 120 s) expires.
  For searches expected to run longer, use the manual SID workflow above.

- **`splunk_search_export` is one-shot** — no SID, no pagination, results stream back immediately.
  Use it when you know the query is fast but the result set is large.

- **REST metadata is best-effort** — `splunk_get_index_info` size/retention fields may be empty
  if the service account lacks `list_storage_passwords` or `indexes_edit` capability.

- **App scoping matters** — `splunk_list_saved_searches`, `splunk_list_macros`, and
  `splunk_list_dashboards` all accept an `app` parameter. Without it they search all apps,
  which can return duplicates if the same name exists in multiple apps.

- **`splunk_get_object_acl` object_type** must be the REST endpoint path fragment, e.g.
  `saved/searches`, `data/inputs/monitor`, `admin/macros`.

---

## SPL Pattern Cheatsheet

```spl
# Count events by field
index=main | stats count by host, sourcetype

# Time-series chart
index=main error | timechart span=1h count by host

# Top N values
index=main | top limit=10 uri

# Extract fields with regex
index=main | rex "user=(?P<username>\\w+)"

# Conditional field
index=main | eval severity=if(status>=500, "error", "ok")

# Lookup enrichment
index=main | lookup asset_lookup ip AS src_ip OUTPUT owner

# Session grouping
index=main | transaction session_id maxspan=30m maxpause=5m

# Filter then aggregate
index=main status=200 | stats avg(response_time) as avg_ms by uri | where avg_ms > 1000

# Field summary (data profiling)
index=main | fieldsummary maxvals=3 | table field count distinct_count is_exact values
```
