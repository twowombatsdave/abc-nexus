#!/usr/bin/env python3
"""
Generic AWS SAM Deploy Script

Deploys AWS SAM stack for any serverless application.
Supports both dev and prod stages with configurable parameters.
"""

import argparse
import subprocess
import sys
import os
from typing import Optional

def run(cmd: str) -> None:
    """
    Runs a shell command and raises if it fails.
    """
    print(f"\n>>> {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    parser = argparse.ArgumentParser(
        description="Deploy AWS SAM stack"
    )
    parser.add_argument(
        'stage', choices=['dev', 'prod'],
        help="Deployment stage ('dev' or 'prod')"
    )
    parser.add_argument(
        '--profile', default=None,
        help="Optional AWS CLI profile name"
    )
    parser.add_argument(
        '--project-name', default=None,
        help="Project name (defaults to directory name)"
    )
    parser.add_argument(
        '--notification-email', default=None,
        help="Email address for error notifications"
    )
    parser.add_argument(
        '--skip-build', action='store_true',
        help="Skip the build step (useful for quick redeploys)"
    )
    parser.add_argument(
        '--region', default='us-east-1',
        help="AWS region for deployment"
    )

    args = parser.parse_args()

    # Set default project name if not provided
    if not args.project_name:
        args.project_name = os.path.basename(os.getcwd())

    # Set default notification email if not provided
    if not args.notification_email:
        args.notification_email = f"admin@{args.project_name}.com"

    profile_opt = f"--profile {args.profile}" if args.profile else ""

    # Build parameters
    parameter_overrides = f'--parameter-overrides ProjectName={args.project_name} StageName={args.stage} NotificationEmail={args.notification_email}'

    try:
        if not args.skip_build:
            print(f"🔨 Building SAM application for {args.stage}...")
            run(f"sam build --use-container {profile_opt}")

        print(f"🚀 Deploying to {args.stage}...")
        run(f"sam deploy --stack-name {args.project_name}-{args.stage} --region {args.region} --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM {parameter_overrides} --resolve-s3 --no-confirm-changeset --no-fail-on-empty-changeset {profile_opt}")

        print(f"\n✅ Deployment to {args.stage} completed successfully!")
        print(f"\n📋 Next steps:")
        print(f"1. Check the CloudFormation outputs for resource URLs")
        print(f"2. Test your API endpoints")
        print(f"3. Configure any additional services as needed")

    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()