# AGENTS.md

### Project Automation Guidelines

### Strict Rule: Terminal & CLI First Policy

You (the AI Agent) have complete command-line and terminal access to this environment. You must maximize your autonomy using CLIs and never delegate web-based infrastructure tasks to the human operator. 

### 1. Prohibited Requests

* **NEVER** ask the operator to manually open a browser or log into dashboards (such as Vercel, Railway, Supabase, Netlify, AWS, or GitHub web).
* **NEVER** ask the operator to manually create projects, trigger deployments, set environment variables, or check build logs inside a web user interface.

### 2. Autonomous Execution Flow

* **CLI Over Web UI:** If an infrastructure action is needed, immediately use the respective terminal tool (e.g., vercel, railway, gh).
* **Session Verification:** Before asking for credentials, autonomously check if a session exists using commands like vercel whoami, railway whoami, or gh auth status.
* **Deployments & Variables:** Always use execution commands (e.g., vercel deploy, railway up) and pipe/inject environment variables directly via the CLI tool tools instead of requesting manual copy-pasting.

### 3. Allowed Exceptions

You may only prompt the human operator regarding external platforms if: 

* The CLI tool explicitly requires a browser-based OAuth validation link that your environment cannot automatically bypass.
* There is a terminal-blocking account restriction (e.g., payment failure or missing team permissions) that cannot be handled programmatically.
