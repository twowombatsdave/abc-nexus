# Twinit Template

A production-ready AWS SAM template for serverless applications with GitHub Actions CI/CD, error handling, and monitoring.

**Use this template**: Click "Use this template" on GitHub to create a new repository from this template.

## Architecture

This template provides a solid foundation with:

- **API Gateway**: REST API endpoint
- **Lambda Functions**: Serverless compute
- **S3 Bucket**: Data storage with lifecycle policies
- **SQS Queue**: Message processing
- **SNS Topic**: Notifications and alerts
- **Error Handling**: Automatic error monitoring with Lambda Destinations

## Quick Start

### Prerequisites

- AWS CLI configured
- SAM CLI installed
- Python 3.12+

### Setup

1) Clone
```bash
git clone <your-repo>
cd <project-name>
```

2) Configure `samconfig.toml`
- Set per‑env values: `ProjectName`, `StageName`, `SlackChannelId`, `AsanaParentTaskGid`.

3) Create Secrets Manager secrets (once per region)
```bash
aws secretsmanager create-secret --name slack-bot-token --secret-string 'xoxb-…' --region eu-west-1
aws secretsmanager create-secret --name asana-pat       --secret-string '2/…'   --region eu-west-1
```

4) Deploy
```bash
sam build && sam deploy --config-env dev
# or
sam build && sam deploy --config-env prod
```

## Project Structure

```
├── template.yaml              # SAM template
├── samconfig.toml            # SAM configuration
├── deploy.py                 # Deployment script
├── src/                      # Lambda function code
│   └── handler.py           # Main Lambda handler
├── error_handler/            # Error handling Lambda
│   └── error_handler.py     # Error processing function
└── config/                   # Configuration files
    ├── secrets.json.example # Secrets template
    └── service_account.json # Service account credentials
```

## Configuration

### Parameters (template.yaml)

- `ProjectName`: Logical name prefix for resources
- `StageName`: Deployment stage (dev/prod)
- `NotificationEmail`: Email for error notifications
- `SlackChannelId`: Slack channel ID for AWS errors
- `AsanaParentTaskGid`: Asana parent task for error subtasks
- `SlackBotTokenSecretName`, `AsanaPatSecretName`: names of Secrets Manager entries

### GitHub secrets
Set these for workflows:
- `SLACK_CHANNEL_ID`, `SLACK_BOT_TOKEN`
- `ASANA_PARENT_TASK_GID`, `ASANA_PAT`
- `GOOGLE_SERVICE_ACCOUNT` (JSON) for the sheet seeding workflow

## Development

### Local Development

```bash
# Start local API
sam local start-api

# Invoke function locally
sam local invoke ProcessFunction
```

### Project bootstrap helper (setup.sh)

Use `setup.sh` to standardize local env setup and Python deps:

- What it does
  - Reads `config/secrets.json` (if present) and exports DBT env vars (`DBT_DATASET`, profiles, project dir)
  - Creates/activates a local virtualenv at `venv/`
  - Installs `requirements.txt` and runs `dbt deps` when available

- Common commands
```bash
# Normal setup (idempotent): create/activate venv, install deps, load DBT env
./setup.sh

# Copy shared dev credentials from ../dev-projects/config into this repo's ./config
./setup.sh --config

# Save current pip env to requirements.txt (activates venv if needed)
./setup.sh --save    # or -s

# Clear requirements.txt and recreate a fresh venv (nukes ./venv)
./setup.sh --clear   # or -c

# Force recreate venv without touching requirements.txt
./setup.sh --new     # or -n

# Help
./setup.sh --help    # flags and combined options
```

Notes
- Run with `bash setup.sh` or `./setup.sh` (it is a bash script, not Python).
- The script prefers `python3` and uses `venv/bin/pip` to avoid mixing system/site packages.
- If `dbt` is installed, the script runs `dbt deps` automatically.

### Zero-touch repo creation (tw-init.sh)

You can generate a brand new project from this template anywhere in WSL with a single command.

What `tw-init.sh` does
- Creates a new repo directory under `~/dev-projects/<project-name>` using this template
- Runs `./setup.sh --config` to pull shared config into `./config`
- Opens the project in Cursor

Example alias (add to `~/.bashrc`)
```bash
# tw-init <project-name> → clones from template, configures, opens in Cursor
alias tw-init='bash ~/scripts/tw-init.sh'

# Reload shell after editing bashrc
source ~/.bashrc
```

Usage
```bash
tw-init my-new-service
```

Assumptions
- The script writes projects under `~/dev-projects/`
- It has access to a GitHub token or uses the GitHub CLI to create a repo from this template
- `cursor` is on PATH so the project opens automatically

### Testing

```bash
# Run tests
python -m pytest tests/

# Test specific function
sam local invoke ProcessFunction --event events/test-event.json
```

## Deployment

### Manual Deployment

```bash
# Build and deploy
sam build
sam deploy --guided

# Or use the deploy script
python deploy.py dev
```

### CI/CD

- `deploy_to_aws.yml` → manual deploy with stack outputs posted to Slack
- `issue_triggered.yml` → issue-labeled trigger; Slack notify and auto-close
- `dbt_seed_and_run.yml` → dbt deps/seed/run
- `sheet_seed.yml` → Google Sheet → BigQuery seed (inline constants)

## Error Handling

The template includes comprehensive error handling:

1. API failures are forwarded to the error SQS (sync safe)
2. Async failures via Lambda Destinations go to the same queue
3. Error handler posts to Slack, creates Asana subtask (assignee "me"), and publishes SNS
4. Correlation IDs propagate end‑to‑end and are included in notifications

Test quickly:
```bash
curl -X POST "https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/process?forceError=true"
```

## Monitoring

### CloudWatch Logs

- Function logs: `/aws/lambda/{project}-{stage}-{function}`
- Error logs: `/aws/lambda/{project}-{stage}-error-handler`
- Logs Insights query by correlationId:
```sql
fields @timestamp, @log, @message
| filter @message like /corr=YOUR_ID/
| sort @timestamp asc
```

### SNS Notifications

Error notifications are sent to the configured email address with:
- Error category and priority
- Function name and request ID
- Stack trace and input payload

## Customization

### Adding New Functions

1. Add function to `template.yaml`
2. Create handler in `src/`
3. Configure permissions and events

### Adding New Resources

1. Define resource in `template.yaml`
2. Update function permissions
3. Add outputs if needed

### Environment Variables

Add environment variables to functions in `template.yaml`:

```yaml
Environment:
  Variables:
    CUSTOM_VAR: !Ref CustomParameter
```

## Google Sheet → BigQuery seeding

- Script: `dbt/sheet_to_bigquery.py`
- Workflow: `.github/workflows/sheet_seed.yml` (edit constants for your sheet and table)
- Requires `GOOGLE_SERVICE_ACCOUNT` GitHub secret (service account must be a member of the Shared Drive)

## Troubleshooting

### Common Issues

1. **Permission Errors**: Check IAM policies in template
2. **Timeout Errors**: Increase function timeout
3. **Memory Issues**: Increase function memory

### Debugging

```bash
# View logs
sam logs -n ProcessFunction --stack-name my-project-dev

# Test locally
sam local invoke ProcessFunction --debug
```