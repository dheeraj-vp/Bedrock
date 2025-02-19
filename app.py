import boto3
import botocore.config
import json
from datetime import datetime

def qa_generate_using_bedrock(question: str, image_base64: str = None) -> str:
    """
    Sends a text or text + image request to Amazon Bedrock using Claude-3 Haiku and returns the response.
    """
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": []
            }
        ]
    }

    # Add text content
    if question:
        body["messages"][0]["content"].append({"type": "text", "text": question})

    # Add image content if provided
    if image_base64:
        body["messages"][0]["content"].append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_base64
            }
        })

    if not body["messages"][0]["content"]:
        return "No valid input provided."

    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                               config=botocore.config.Config(read_timeout=300, retries={'max_attempts': 3}))
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(body)
        )
        
        response_content = response["body"].read().decode("utf-8")
        response_data = json.loads(response_content)

        # Extract response text from Bedrock
        if "content" in response_data and isinstance(response_data["content"], list):
            return response_data["content"][0].get("text", "No response text found.")
        else:
            print("Invalid response format:", response_data)
            return "Error: Invalid response format."

    except Exception as e:
        print(f"Error generating the answer: {e}")
        return "Error: Unable to process the request."

def save_qa_details_s3(s3_key, s3_bucket, answer):
    """
    Saves the generated answer to an S3 bucket.
    """
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=answer.encode("utf-8"))
        print(f"Answer saved to S3: {s3_key}")
    except Exception as e:
        print(f"Error saving the answer to S3: {e}")

def lambda_handler(event, context):
    """
    AWS Lambda function handler that processes an incoming event, extracts a question and image,
    generates an answer using Bedrock, and saves the output to S3.
    """
    try:
        event_body = event.get("body", "{}")
        event_data = json.loads(event_body)
        
        question = event_data.get("question", "").strip()
        image_base64 = event_data.get("image_base64", "").strip() or None  # Handle empty string as None

        if not question and not image_base64:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Question or image is required'})}

        answer = qa_generate_using_bedrock(question, image_base64)

        if answer:
            current_time = datetime.now().strftime('%Y%m%d%H%M%S')
            s3_key = f"qa-output/{current_time}.txt"
            s3_bucket = "awsbedrockcalquity"
            save_qa_details_s3(s3_key, s3_bucket, answer)
        else:
            print("No answer was generated")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Question Answering process completed', 'answer': answer})
        }

    except Exception as e:
        print(f"Error in Lambda execution: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal Server Error'})}
