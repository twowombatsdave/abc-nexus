import os
import json
import logging
import base64
import zlib
from datetime import datetime, timezone
import boto3
from typing import Dict, Any
import urllib.request
import urllib.error
import socket

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'my-project')
STAGE_NAME = os.environ.get('STAGE_NAME', 'dev')

# Optional downstream integrations (Slack and Asana)
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')

ASANA_PAT = os.environ.get('ASANA_PAT')
ASANA_PARENT_TASK_GID = os.environ.get('ASANA_PARENT_TASK_GID')

# AWS clients
sns = boto3.client('sns')


def extract_error_details(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract error details from a failed Lambda execution record.
    """
    try:
        # Initialize default values
        function_name = 'Unknown'
        function_arn = ''
        error_message = 'Unknown error'
        error_type = 'Unknown'
        stack_trace = []
        request_id = 'Unknown'
        timestamp = datetime.now(timezone.utc).isoformat()
        input_payload = {}

        # Extract from Lambda Destinations format
        if 'requestContext' in record and 'responsePayload' in record:
            try:
                request_context = record.get('requestContext', {})
                response_payload = record.get('responsePayload', {})

                # Extract function name from function ARN
                function_arn = request_context.get('functionArn', '')
                if function_arn:
                    arn_parts = function_arn.split(':')
                    if len(arn_parts) >= 7:
                        function_name = arn_parts[6]
                        if function_name == '$LATEST' and len(arn_parts) >= 6:
                            function_name = arn_parts[5]
                    elif len(arn_parts) >= 6:
                        function_name = arn_parts[5]

                # Extract error details
                error_message = response_payload.get('errorMessage', 'Unknown error')
                error_type = response_payload.get('errorType', 'Unknown')
                stack_trace = response_payload.get('stackTrace', [])
                request_id = request_context.get('requestId', 'Unknown')
                correlation_id = request_context.get('correlationId', '')
                timestamp = record.get('timestamp', timestamp)
                input_payload = record.get('requestPayload', {})

            except Exception as e:
                logger.warning(f"Failed to extract from Lambda Destinations: {e}")

        # Fallback to standard Lambda event structure
        if function_name == 'Unknown':
            request_context = record.get('requestContext', {})
            function_name = request_context.get('functionName', 'Unknown')
            function_arn = request_context.get('functionArn', '')
            error_message = record.get('errorMessage', error_message)
            error_type = record.get('errorType', error_type)
            stack_trace = record.get('stackTrace', stack_trace)
            request_id = request_context.get('requestId', request_id)
            timestamp = record.get('timestamp', timestamp)
            input_payload = record.get('input', input_payload)

        # Extract from DLQ message body
        if function_name == 'Unknown' and 'body' in record:
            try:
                body = json.loads(record['body']) if isinstance(record['body'], str) else record['body']
                function_name = body.get('functionName', function_name)
                error_message = body.get('errorMessage', error_message)
                error_type = body.get('errorType', error_type)
                request_id = body.get('requestId', request_id)
                timestamp = body.get('timestamp', timestamp)
                input_payload = body.get('input', input_payload)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse DLQ message body: {e}")

        return {
            'function_name': function_name,
            'function_arn': function_arn,
            'error_type': error_type,
            'error_message': error_message,
            'stack_trace': stack_trace,
            'request_id': request_id,
            'timestamp': timestamp,
            'input_payload': input_payload,
            'correlation_id': correlation_id if 'correlation_id' in locals() and correlation_id else (input_payload.get('correlation_id') if isinstance(input_payload, dict) else ''),
            'project': PROJECT_NAME,
            'stage': STAGE_NAME
        }

    except Exception as e:
        logger.error(f"Failed to extract error details: {e}")
        return {
            'function_name': f"{PROJECT_NAME}-{STAGE_NAME}-unknown-function",
            'error_type': 'ParseError',
            'error_message': f'Failed to parse error record: {e}',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'project': PROJECT_NAME,
            'stage': STAGE_NAME
        }


def determine_error_category(error_type: str, error_message: str) -> str:
    """
    Categorize errors for better notification handling.
    """
    error_lower = error_message.lower()

    if 'permission' in error_lower or 'forbidden' in error_lower:
        return 'PERMISSION_ERROR'
    elif 'rate' in error_lower or 'throttle' in error_lower:
        return 'RATE_LIMITED'
    elif 'timeout' in error_lower:
        return 'TIMEOUT_ERROR'
    elif 'network' in error_lower or 'connection' in error_lower:
        return 'NETWORK_ERROR'
    else:
        return 'GENERAL_ERROR'


def send_error_notification(error_details: Dict[str, Any]) -> None:
    """
    Send error notification via SNS.
    """
    try:
        error_category = determine_error_category(
            error_details.get('error_type', ''),
            error_details.get('error_message', '')
        )

        # Create subject based on error category
        if error_category == 'PERMISSION_ERROR':
            subject = f"⚠️  {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Permission Error"
            priority = "HIGH"
        elif error_category == 'RATE_LIMITED':
            subject = f"⏱️  {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Rate Limited"
            priority = "MEDIUM"
        elif error_category == 'TIMEOUT_ERROR':
            subject = f"⏰ {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Timeout Error"
            priority = "HIGH"
        elif error_category == 'NETWORK_ERROR':
            subject = f"🌐 {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Network Error"
            priority = "MEDIUM"
        else:
            subject = f"❌ {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Lambda Error"
            priority = "MEDIUM"

        # Create message body
        message_body = f"""
Lambda Function Error Alert

Project: {PROJECT_NAME.upper()} ({STAGE_NAME.upper()})
Function: {error_details.get('function_name', 'Unknown')}
Error Type: {error_details.get('error_type', 'Unknown')}
Error Category: {error_category}
Priority: {priority}
Request ID: {error_details.get('request_id', 'Unknown')}
Timestamp: {error_details.get('timestamp', 'Unknown')}
CorrelationId: {error_details.get('correlation_id', '') or 'n/a'}

Error Message:
{error_details.get('error_message', 'No message available')}

Stack Trace:
{chr(10).join(error_details.get('stack_trace', ['No stack trace available']))}

Input Payload:
{json.dumps(error_details.get('input_payload', {}), indent=2)}
        """.strip()

        # Send SNS notification
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message_body,
            MessageAttributes={
                'error_category': {
                    'DataType': 'String',
                    'StringValue': error_category
                },
                'function_name': {
                    'DataType': 'String',
                    'StringValue': error_details.get('function_name', 'Unknown')
                },
                'priority': {
                    'DataType': 'String',
                    'StringValue': priority
                },
                'correlation_id': {
                    'DataType': 'String',
                    'StringValue': error_details.get('correlation_id', '') or 'n/a'
                }
            }
        )

        logger.info(f"Sent error notification for {error_details.get('function_name')} - MessageId: {response.get('MessageId')}")

    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")


def _http_post_json(url: str, headers: Dict[str, str], data_obj: Dict[str, Any], timeout_seconds: int = 8) -> Dict[str, Any]:
    try:
        payload = json.dumps(data_obj).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode('utf-8')
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return { 'ok': False, 'raw': body }
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8') if hasattr(e, 'read') else ''
        logger.error(f"HTTPError POST {url}: {e.code} {raw}")
        return { 'ok': False, 'status': e.code, 'error': raw }
    except (urllib.error.URLError, socket.timeout) as e:
        logger.error(f"URLError POST {url}: {e}")
        return { 'ok': False, 'error': str(e) }


def send_slack_message(error_details: Dict[str, Any]) -> None:
    """
    Send a Slack message via chat.postMessage using SLACK_BOT_TOKEN and SLACK_CHANNEL_ID.
    No-op if env vars are not configured.
    """
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        logger.info("Slack env vars not set; skipping Slack notification")
        return

    text = (
        f"❌ {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - Lambda Error\n"
        f"Function: {error_details.get('function_name', 'Unknown')}\n"
        f"Type: {error_details.get('error_type', 'Unknown')}\n"
        f"Message: {error_details.get('error_message', 'Unknown')}\n"
        f"When: {error_details.get('timestamp', 'Unknown')}\n"
        f"CorrelationId: {error_details.get('correlation_id', '') or 'n/a'}\n"
    )

    url = 'https://slack.com/api/chat.postMessage'
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    data_obj = {
        'channel': SLACK_CHANNEL_ID,
        'text': text
    }
    resp = _http_post_json(url, headers, data_obj)
    if not resp or not resp.get('ok', False):
        logger.error(f"Slack post failed: {resp}")
    else:
        logger.info("Slack notification sent successfully")


def create_asana_error_subtask(error_details: Dict[str, Any]) -> None:
    """
    Create an Asana subtask under ASANA_PARENT_TASK_GID using ASANA_PAT.
    If ASANA_PROJECT_GID is provided, you can switch to creating a task with parent+project
    via POST /tasks instead. For simplicity here we use the subtasks endpoint.
    No-op if env vars are not configured.
    """
    if not ASANA_PAT or not ASANA_PARENT_TASK_GID:
        logger.info("Asana env vars not set; skipping Asana subtask creation")
        return

    name = f"❌ {PROJECT_NAME.upper()} {STAGE_NAME.upper()} - {error_details.get('function_name', 'Unknown')}"
    notes = (
        f"Error Type: {error_details.get('error_type', 'Unknown')}\n"
        f"Message: {error_details.get('error_message', 'Unknown')}\n"
        f"When: {error_details.get('timestamp', 'Unknown')}\n"
        f"Request ID: {error_details.get('request_id', 'Unknown')}\n"
        f"CorrelationId: {error_details.get('correlation_id', '') or 'n/a'}\n\n"
        f"Stack Trace:\n{chr(10).join(error_details.get('stack_trace', ['No stack trace available']))}\n"
    )

    url = f"https://app.asana.com/api/1.0/tasks/{ASANA_PARENT_TASK_GID}/subtasks"
    headers = {
        'Authorization': f'Bearer {ASANA_PAT}',
        'Content-Type': 'application/json'
    }
    data_obj = {
        'data': {
            'name': name,
            'notes': notes,
            'assignee': 'me'
        }
    }
    resp = _http_post_json(url, headers, data_obj)
    if not resp or (isinstance(resp, dict) and not resp.get('data')):
        logger.error(f"Asana subtask creation failed: {resp}")
    else:
        gid = resp.get('data', {}).get('gid', 'unknown') if isinstance(resp, dict) else 'unknown'
        logger.info(f"Asana subtask created: {gid}")


def handler(event, context):
    """
    Process failed Lambda executions from the dead letter queue.
    """
    logger.info(f"Processing {len(event.get('Records', []))} error records from DLQ")

    processed_count = 0
    error_count = 0

    for record in event.get('Records', []):
        try:
            # Extract the actual error record from SQS message
            try:
                error_record = json.loads(record['body'])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse DLQ message body as JSON: {e}")
                error_record = record

            # Extract error details
            error_details = extract_error_details(error_record)

            # Send notification
            send_error_notification(error_details)

            # Also notify Slack and Asana (best-effort; failures here should not stop processing)
            try:
                send_slack_message(error_details)
            except Exception as slack_err:
                logger.error(f"Slack notification failed: {slack_err}")

            try:
                create_asana_error_subtask(error_details)
            except Exception as asana_err:
                logger.error(f"Asana subtask creation failed: {asana_err}")

            processed_count += 1
            logger.info(f"Processed error record for function: {error_details.get('function_name')}")

        except Exception as e:
            error_count += 1
            logger.error(f"Failed to process error record: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'errors': error_count,
            'message': f'Processed {processed_count} error records, {error_count} failed to process'
        })
    }