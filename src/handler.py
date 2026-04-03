import json
from datetime import datetime, timezone
import uuid
import logging
import os
import boto3
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
BUCKET_NAME = os.environ['BUCKET_NAME']
QUEUE_URL = os.environ['QUEUE_URL']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
ERROR_QUEUE_URL = os.environ.get('ERROR_QUEUE_URL')

# AWS clients
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
sns = boto3.client('sns')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function.

    This is a generic handler that can be customized for your specific use case.
    """
    logger.info(f"Processing event: {json.dumps(event)}")

    try:
        # Extract data from event
        if 'Records' in event:
            # SQS event
            for record in event['Records']:
                process_sqs_record(record)
        else:
            # API Gateway event
            process_api_event(event, context)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing completed successfully',
                'timestamp': context.aws_request_id
            })
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        # Forward failure to error queue for unified handling (Slack/Asana) then re-raise
        try:
            headers = (event or {}).get('headers') or {}
            correlation_id = headers.get('X-Correlation-Id') or getattr(context, 'aws_request_id', None) or str(uuid.uuid4())
            if ERROR_QUEUE_URL:
                sqs.send_message(
                    QueueUrl=ERROR_QUEUE_URL,
                    MessageBody=json.dumps({
                        "requestContext": {
                            "functionArn": getattr(context, 'invoked_function_arn', ''),
                            "requestId": getattr(context, 'aws_request_id', 'unknown'),
                            "correlationId": correlation_id
                        },
                        "responsePayload": {
                            "errorMessage": str(e),
                            "errorType": type(e).__name__,
                            "stackTrace": []
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                )
        except Exception as forward_err:
            logger.error(f"Failed to forward error to SQS: {forward_err}")
        raise e


def process_sqs_record(record: Dict[str, Any]) -> None:
    """
    Process a single SQS record.
    """
    try:
        # Parse the message body
        message_body = json.loads(record['body'])
        logger.info(f"Processing SQS message: {message_body}")

        # Your processing logic here
        result = process_data(message_body)

        # Store result in S3
        store_result(result)

        logger.info("SQS record processed successfully")

    except Exception as e:
        logger.error(f"Error processing SQS record: {str(e)}")
        raise e


def process_api_event(event: Dict[str, Any], context: Any) -> None:
    """
    Process an API Gateway event.
    """
    try:
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')

        headers = event.get('headers') or {}
        correlation_id = headers.get('X-Correlation-Id') or getattr(context, 'aws_request_id', None) or str(uuid.uuid4())
        logger.info(f"[corr={correlation_id}] Processing API request: {http_method} {path}")

        # Force an intentional error for testing end-to-end error flow
        # Trigger via: POST /process with body {"forceError": true} or query ?forceError=true
        qs = event.get('queryStringParameters') or {}
        body_raw = event.get('body', '{}')
        body = json.loads(body_raw) if isinstance(body_raw, str) else (body_raw or {})
        if str(qs.get('forceError', 'false')).lower() in ['1', 'true', 'yes'] or \
           str(body.get('forceError', 'false')).lower() in ['1', 'true', 'yes']:
            raise RuntimeError('Forced test error to validate error pipeline')

        # Your API logic here
        if http_method == 'POST' and path == '/process':
            result = process_data(body)

            # Send message to SQS with correlation envelope for async processing
            envelope = {
                "correlationId": correlation_id,
                "source": "api",
                "triggerType": "apiGateway",
                "requestId": getattr(context, 'aws_request_id', 'unknown'),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": result
            }
            send_to_queue(envelope)

        logger.info(f"[corr={correlation_id}] API event processed successfully")

    except Exception as e:
        logger.error(f"Error processing API event: {str(e)}")
        raise e


def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the input data.

    Customize this function for your specific business logic.
    """
    logger.info(f"Processing data: {data}")

    # Example processing logic
    result = {
        'processed_at': context.aws_request_id,
        'input_data': data,
        'status': 'processed'
    }

    return result


def store_result(result: Dict[str, Any]) -> None:
    """
    Store processing result in S3.
    """
    try:
        key = f"results/{context.aws_request_id}.json"

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        logger.info(f"Result stored in S3: s3://{BUCKET_NAME}/{key}")

    except Exception as e:
        logger.error(f"Error storing result in S3: {str(e)}")
        raise e


def send_to_queue(data: Dict[str, Any]) -> None:
    """
    Send data to SQS queue for processing.
    """
    try:
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(data)
        )

        logger.info("Message sent to SQS queue")

    except Exception as e:
        logger.error(f"Error sending message to SQS: {str(e)}")
        raise e


def send_notification(message: str, subject: str = "Processing Notification") -> None:
    """
    Send notification via SNS.
    """
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )

        logger.info("Notification sent via SNS")

    except Exception as e:
        logger.error(f"Error sending SNS notification: {str(e)}")
        raise e
