# lambda/index.py
import json
import os
import boto3
import re
import urllib.request  # ★追加
import urllib.error    # ★追加
from botocore.exceptions import ClientError

def extract_region_from_arn(arn):
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"

bedrock_client = None

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

# 外部APIのエンドポイント（ここにリクエスト送る）
EXTERNAL_API_URL = "https://d6d5-34-16-186-141.ngrok-free.app/generate"  # ★あなたのAPIエンドポイントに変えてね！

def lambda_handler(event, context):
    try:
        global bedrock_client
        if bedrock_client is None:
            region = extract_region_from_arn(context.invoked_function_arn)
            bedrock_client = boto3.client('bedrock-runtime', region_name=region)
            print(f"Initialized Bedrock client in region: {region}")
        
        print("Received event:", json.dumps(event))

        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])

        print("Processing message:", message)
        print("Using model:", MODEL_ID)

        messages = conversation_history.copy()

        messages.append({
            "role": "user",
            "content": message
        })

        bedrock_messages = []
        for msg in messages:
            if msg["role"] == "user":
                bedrock_messages.append({
                    "role": "user",
                    "content": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                bedrock_messages.append({
                    "role": "assistant",
                    "content": [{"text": msg["content"]}]
                })

        request_payload = {
            "messages": bedrock_messages,
            "inferenceConfig": {
                "maxTokens": 512,
                "stopSequences": [],
                "temperature": 0.7,
                "topP": 0.9
            }
        }

        print("Calling External API with payload:", json.dumps(request_payload))

        # ★★ ここを変更 ★★
        try:
        # リクエスト作成
        req = urllib.request.Request(
            EXTERNAL_API_URL,
            data=json.dumps(request_payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        
        # リクエスト送信
        with urllib.request.urlopen(req) as res:
            res_data = res.read()
            response_body = json.loads(res_data)
        
        # 受け取った内容を使う
        print("✅ 受け取った応答:", json.dumps(response_body, indent=2, ensure_ascii=False))
    
        except urllib.error.HTTPError as e:
            print("❌ HTTPエラー:", e.code)
            print(e.read().decode())
        except urllib.error.URLError as e:
            print("❌ 接続エラー:", e.reason)

        print("Bedrock response:", json.dumps(response_body, default=str))
        
        if not response_body.get('output') or not response_body['output'].get('message') or not response_body['output']['message'].get('content'):
            raise Exception("No response content from the model")

        assistant_response = response_body['output']['message']['content'][0]['text']

        messages.append({
            "role": "assistant",
            "content": assistant_response
        })

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }

    except Exception as error:
        print("Error:", str(error))
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
