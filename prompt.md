# Build: Hermes Cron Operations Extension

Implement a lightweight,  native Hermes extension for centralized cron management across all profiles.

Use the completed Cron Operations feasibility report as the architectural reference. Inspect the actual Hermes installation, plugin interfaces, and existing cron implementation before coding.

### Architecture

Build a native Hermes plugin containing:

- A CLI interface: `hermes cronops`
- A bundled `cron-ops` skill.
- Python modules for inventory, scheduling validation, metrics, and management.
- SQLite storage using Hermes `plugin_db()`.

Use Python standard library wherever possible. Avoid external services, background daemons, heavyweight dependencies, and modifications to Hermes core.

### Features

**1. Centralized inventory**

- Discover cron jobs across all profiles.
- Display job ID, name, profile, schedule, model, execution type, and status.
- Support filtering by profile and status.

**2. Schedule validation**

- Detect existing agent-backed jobs scheduled within ±45 minutes.
- Account for recurring schedules, execution duration, and profile timezones.
- Recommend alternative execution times.
- Clearly distinguish warnings from actual execution overlaps.

**3. Execution metrics**

- Display the last 10 executions per job.
- Collect duration, tokens, model, success/failure, errors, and delivery outcomes.
- Calculate deterministic complexity classifications.
- Report unavailable CPU/RAM metrics as unknown.
- Avoid duplicating Hermes execution records.

**4. Cross-profile management**
Provide commands to inspect, pause, resume, delete, and manage jobs across profiles.
Use Hermes-native CLI/API operations for all modifications. Never directly modify internal cron configuration files or databases.

**5. Bundled skill**
Create a `cron-ops` skill explaining how agents should:

- Discover existing jobs.
- Validate schedules before creating jobs.
- Check execution metrics.
- Manage jobs across profiles.
- Follow scheduling and resource policies.

### Implementation requirements

- Follow the installed Hermes plugin architecture and public APIs.
- Keep all persistent extension data inside `plugin_db()`.
- Preserve Hermes as the single source of truth.
- Handle missing profiles, malformed configurations, database errors, and unsupported schema versions gracefully.
- Keep commands concise and provide human-readable output.
- Support machine-readable JSON output.
- Never expose credentials or sensitive configuration values.

### Development sequence

1. Implement plugin structure and centralized inventory.
2. Implement execution history and metrics.
3. Implement timezone-aware schedule validation and recommendations.
4. Implement cross-profile management.
5. Bundle the skill and integrate CLI commands.
6. Run plugin validation, unit tests, integration tests, and safe operational tests.

Keep CPU/RAM sampling out of v1. Design the metrics interface so it can be added later without architectural changes.

### Acceptance criteria

- All existing profiles are discovered correctly.
- Jobs are not duplicated in the inventory.
- The last 10 executions are correctly associated with each job.
- Schedule conflicts are detected accurately.
- Cross-profile operations use Hermes-native mechanisms.
- The plugin installs and validates without modifying Hermes core.
- The skill is discoverable and usable by Hermes agents.
- No unnecessary background processes are introduced.

Work directly in the appropriate plugin development directory. Inspect existing conventions before implementation.

Complete the implementation, ask me to test it manually on ubuntu machine, and provide a concise report covering files created, commands available, validation results, limitations, and installation instructions.

Do not stop at producing an implementation plan.

# Inventory
hermes cronops list
hermes cronops list --profile research
hermes cronops list --status running

# Schedule validation
hermes cronops validate "0 9 * * *"
hermes cronops validate "0 9 * * *" --profile default

# Metrics
hermes cronops metrics <job-id>
hermes cronops history <job-id> --limit 10

# Management
hermes cronops inspect <job-id>
hermes cronops pause <job-id>
hermes cronops resume <job-id>
hermes cronops delete <job-id>

# Diagnostics
hermes cronops doctor