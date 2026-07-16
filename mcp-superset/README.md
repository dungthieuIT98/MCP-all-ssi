# Superset MCP Integration
[![smithery badge](https://smithery.ai/badge/@aptro/superset-mcp)](https://smithery.ai/server/@aptro/superset-mcp)

MCP server for interacting with Apache Superset, enabling AI agents to connect to and control a Superset instance programmatically.

## Setup Instructions

### Installing via Smithery

To install Superset Integration for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@aptro/superset-mcp):

```bash
npx -y @smithery/cli install @aptro/superset-mcp --client claude
```

### Manual Installation

1. **Set Up Superset Locally**

   Run this script to start Superset locally:
   ```bash
   git clone --branch 4.1.1 --depth 1 https://github.com/apache/superset && \
   cd superset && \
   docker compose -f docker-compose-image-tag.yml up
   ```

   Once Superset is running, you should be able to access it at http://localhost:8088 with default credentials:
   - Username: admin
   - Password: admin

2. **Clone This Repository**

   Clone this repository to your local machine.

3. **Configure Environment Variables**

   Create a `.env` file in the root directory. The server only needs to know
   where Superset lives — it stores **no** credentials of its own:
   ```
   SUPERSET_BASE_URL=http://localhost:8088  # Change to your Superset URL
   ```

   Authentication is **per-user, session-only**: each MCP request must carry the
   caller's own Superset Flask `session` cookie in the `X-Superset-Session`
   header. Superset issues that cookie on any successful web login (including
   Azure AD / OAuth). The server never holds a username/password, JWT, or
   service-account — it simply forwards the caller's session, preserving their
   real identity, roles, and row-level security.

4. **Install Dependencies**

   ```bash
   uv pip install .
   ```

5. **Install MCP Config for Claude**

   To use with Claude Desktop app:
   ```bash
   mcp install main.py
   ```

## Usage with Claude

After setup, you can interact with your Superset instance via Claude using natural language requests. This server is **read-only** — it only exposes list/get tools, no create/update/delete. Here are some examples:

### Dashboards

- **View dashboards**: "Show me all my Superset dashboards"
- **Get dashboard details**: "Show me the details of dashboard with ID 5"

### Charts

- **List all charts**: "What charts do I have in my Superset instance?"
- **View chart details**: "Show me the details of chart with ID 10"

### Datasets

- **List datasets**: "What datasets are available in my Superset instance?"
- **Get dataset details**: "Show me the details of dataset with ID 3"

### User and Activity

- **View user info**: "Who am I logged in as?"
- **Get user roles**: "What roles do I have in Superset?"
- **View recent activity**: "Show me recent activity in my Superset instance"

### Tags

- **List tags**: "Show me all tags in my Superset instance"
- **Get tag details**: "Show me the details of tag with ID 5"
- **See tagged objects**: "What objects are tagged in my Superset instance?"

### Chart Exploration

- **Get form data**: "Get the explore form data for key 'abc123'"
- **Get a permalink**: "Get the explore permalink for key 'xyz789'"

## Available MCP Tools

This server only exposes **read-only** tools (list/get). Write operations
(create/update/delete) and the database, SQL Lab, query, saved-query, menu,
and advanced-data-type groups are disabled — query data via the Trino MCP
server instead.

### Authentication
- `superset_auth_check_session_validity` - Check whether the caller's forwarded session cookie is valid

### Dashboards
- `superset_dashboard_list` - List all dashboards
- `superset_dashboard_get_by_id` - Get a specific dashboard

### Charts
- `superset_chart_list` - List all charts
- `superset_chart_get_by_id` - Get a specific chart

### Datasets
- `superset_dataset_list` - List all datasets
- `superset_dataset_get_by_id` - Get a specific dataset

### User Information
- `superset_user_get_current` - Get current user info
- `superset_user_get_roles` - Get user roles

### Activity
- `superset_activity_get_recent` - Get recent activity data

### Tags
- `superset_tag_list` - List all tags
- `superset_tag_get_by_id` - Get a specific tag
- `superset_tag_objects` - Get objects associated with tags

### Exploration Tools
- `superset_explore_form_data_get` - Get form data for chart exploration
- `superset_explore_permalink_get` - Get a permalink for chart exploration

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| SUPERSET_BASE_URL | URL of your Superset instance | http://localhost:8088 |

> The server holds no credentials. Callers authenticate per-request by sending
> their Superset `session` cookie in the `X-Superset-Session` header.

## Troubleshooting

- If you get "Not authenticated", make sure the caller/proxy is sending a valid
  Superset `session` cookie in the `X-Superset-Session` header. Re-login to
  Superset to obtain a fresh cookie if it has expired.
- Make sure Superset is running and accessible at the URL specified in your `.env` file
- Check that you're using a compatible version of Superset (tested with version 4.1.1)
- Ensure the port used by the MCP server is not being used by another application

## Security Notes

- The server stores **no** credentials — no username/password, no JWT, no
  service-account token. It only reads `SUPERSET_BASE_URL` from `.env`.
- Every Superset call is made with the caller's own forwarded `session` cookie,
  so requests run with the real user's identity, roles, and row-level security.
- The session cookie must be supplied per-request in the `X-Superset-Session`
  header, typically injected by a trusted upstream gateway/auth-proxy.
- No credentials are transmitted to Claude or any third parties.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT
