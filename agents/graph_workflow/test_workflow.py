#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import requests
from dotenv import load_dotenv

# .env 로드
load_dotenv(override=True)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "2584329788197961728")

# gcloud를 사용하여 access token 및 project number 획득
def get_gcloud_config():
    try:
        print("🗝️ Getting Access Token and Project details from gcloud...")
        token = subprocess.check_output("gcloud auth print-access-token", shell=True).decode().strip()
        project_number = subprocess.check_output(
            f"gcloud projects describe {PROJECT_ID} --format='value(projectNumber)'", 
            shell=True
        ).decode().strip()
        return token, project_number
    except Exception as e:
        print(f"❌ Error getting gcloud config: {e}")
        sys.exit(1)

def main():
    token, project_number = get_gcloud_config()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    base_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{project_number}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
    
    log_lines = []
    
    def log(message):
        print(message)
        log_lines.append(message)

    log("=== 🗝️ Getting Access Token ===")
    log(f"Project ID: {PROJECT_ID}")
    log(f"Project Number: {project_number}")
    log(f"Reasoning Engine ID: {REASONING_ENGINE_ID}")
    log("")

    # --- Case 0: Session Creation ---
    log("=== 🔄 Case 0: Creating Session via REST API ===")
    session_url = f"{base_url}:query"
    session_payload = {
        "class_method": "create_session",
        "input": {
            "user_id": "test_user"
        }
    }
    
    # curl 명령어 생성
    curl_session = f"curl -X POST {session_url} \\\n  -H \"Authorization: Bearer $(gcloud auth print-access-token)\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{json.dumps(session_payload, ensure_ascii=False)}'"

    # HTTP Request 명세 로깅
    log("👉 [HTTP REQUEST]")
    log(f"POST {session_url}")
    # Authorization 토큰 노출을 마스킹하여 안전하게 로깅
    masked_headers = headers.copy()
    masked_headers["Authorization"] = f"Bearer {token[:10]}...{token[-10:]}"
    log(f"Headers: {json.dumps(masked_headers, indent=2)}")
    log(f"Payload:\n{json.dumps(session_payload, indent=2, ensure_ascii=False)}")
    log("")
    log("💻 [COPYABLE CURL COMMAND]")
    log(curl_session)
    log("")
    
    try:
        response = requests.post(session_url, json=session_payload, headers=headers)
        response_json = response.json()
        log("👈 [HTTP RESPONSE (Raw)]")
        log(json.dumps(response_json, indent=2, ensure_ascii=False))
        
        # SESSION_ID 추출
        session_id = response_json["output"]["id"]
        log(f"✅ Extracted SESSION_ID (string): {session_id}")
        log("")
    except Exception as e:
        log(f"❌ Failed to create session: {e}")
        write_log(log_lines)
        sys.exit(1)

    # Helper function to send streamQuery and parse stream
    def send_query_stream(prompt_case_name, prompt_text, interrupt_id=None, response_key="user response"):
        log(f"=== 💬 {prompt_case_name} ===")
        log(f"Prompt: \"{prompt_text}\"")
        if interrupt_id:
            log(f"Interrupt ID to Resume: {interrupt_id}")
            log(f"Response Key: \"{response_key}\"")
        log("")
        
        stream_url = f"{base_url}:streamQuery"
        
        # input payload 구성
        if interrupt_id:
            # ADK 2.0 uses function_response part under message for resumes
            message_payload = {
                "role": "user",
                "parts": [
                    {
                        "function_response": {
                            "name": "adk_request_input",
                            "id": interrupt_id,
                            "response": {
                                response_key: prompt_text
                            }
                        }
                    }
                ]
            }
        else:
            message_payload = prompt_text

        input_payload = {
            "user_id": "test_user",
            "session_id": session_id,
            "message": message_payload
        }

        query_payload = {
            "class_method": "async_stream_query",
            "input": input_payload
        }
        
        # curl 명령어 생성
        curl_stream = f"curl -X POST {stream_url} \\\n  -H \"Authorization: Bearer $(gcloud auth print-access-token)\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{json.dumps(query_payload, ensure_ascii=False)}'"

        # HTTP Request 명세 로깅
        log("👉 [HTTP REQUEST]")
        log(f"POST {stream_url}")
        log(f"Headers: {json.dumps(masked_headers, indent=2)}")
        log(f"Payload:\n{json.dumps(query_payload, indent=2, ensure_ascii=False)}")
        log("")
        log("💻 [COPYABLE CURL COMMAND]")
        log(curl_stream)
        log("")
        
        extracted_interrupt_id = None
        extracted_response_key = "user response"
        try:
            log("👈 [HTTP RESPONSE (Stream Output)]")
            # Stream=True로 연결
            response = requests.post(stream_url, json=query_payload, headers=headers, stream=True)
            
            # SSE 스트림 파싱
            for line in response.iter_lines():
                if not line:
                    continue
                
                decoded_line = line.decode('utf-8').strip()
                if not decoded_line:
                    continue
                
                # 'data: ' 프리픽스가 붙어있으면 떼어냄
                if decoded_line.startswith("data:"):
                    decoded_line = decoded_line[len("data:"):].strip()
                
                try:
                    event_data = json.loads(decoded_line)
                    # 로그 양식에 맞춰 들여쓰기 출력
                    log(json.dumps(event_data, indent=2, ensure_ascii=False))
                    
                    # interruptId 및 response_schema 동적 추출 시도
                    try:
                        parts = event_data.get("content", {}).get("parts", [])
                        for part in parts:
                            func_call = part.get("function_call", {})
                            if func_call and func_call.get("name") == "adk_request_input":
                                args = func_call.get("args", {})
                                if args and "interruptId" in args:
                                    extracted_interrupt_id = args["interruptId"]
                                    response_schema = args.get("response_schema", {})
                                    if isinstance(response_schema, dict) and response_schema:
                                        extracted_response_key = list(response_schema.keys())[0]
                    except Exception:
                        pass
                except json.JSONDecodeError:
                    # JSON이 아닐 경우 그냥 문자열로 로깅
                    log(decoded_line)
            
            log("")
            log("--- Done ---")
            log("")
        except Exception as e:
            log(f"❌ Error sending query: {e}")
            log("")
            
        return extracted_interrupt_id, extracted_response_key

    # --- Case 1: Initial Prompt Response (HITL 1) ---
    # initial_prompt 노드가 실행되면, 사용자에게 '도시 (필수), 연령대, 취미, 좋아했던 관광지 예시' 정보를 요청하는 RequestInput을 돌려주고 일시 정지(PAUSED) 됩니다.
    interrupt_id_1, key_1 = send_query_stream(
        "Case 1: Initial Prompt & Wait for User Input (HITL 1)", 
        "일정 추천 서비스를 시작해줘."
    )

    # --- Case 2: Concierge Recommendation & Feedback Request (HITL 2) ---
    # 사용자의 대답을 전달하여 initial_prompt의 RequestInput을 Resume합니다.
    # concierge_agent가 실행되어 5개 이상의 구체적인 한국어 일정을 ActivitiesList 포맷으로 생성한 뒤, 
    # get_user_feedback 노드에 도달하여 추천 일정을 보여주고 피드백을 요구하는 또 다른 RequestInput을 반환하고 일시 정지(PAUSED) 됩니다.
    interrupt_id_2, key_2 = send_query_stream(
        "Case 2: Deliver Travel Preferences & Generate Recommendations (HITL 2)",
        "도시: 서울, 연령대: 20대, 취미: 맛집 탐방 및 야간 사진 촬영, 좋아했던 관광지: 경복궁 야간 개장",
        interrupt_id=interrupt_id_1,
        response_key=key_1
    )

    # --- Case 3: User Feedback Loop & Updated Itinerary ---
    # 사용자의 피드백을 전달하여 get_user_feedback의 RequestInput을 Resume합니다.
    # process_feedback 노드가 'loop' 루트를 타고 concierge_agent에 피드백을 주입합니다.
    # 에이전트는 피드백을 반영하여 일정을 수정한 뒤, 다시 get_user_feedback 노드를 지나 사용자 응답을 대기하게 됩니다.
    send_query_stream(
        "Case 3: Provide User Feedback to Update Itinerary (Loop Back)",
        "기본 추천 일정 중 2번 맛집 탐방 대신, '경복궁 야간 한복 체험 및 인생샷 명소 투어'로 일정을 교체하고 상세 설명을 업데이트해줘.",
        interrupt_id=interrupt_id_2,
        response_key=key_2
    )

    write_log(log_lines)

def write_log(log_lines):
    log_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "api_test_results.log")
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
        f.write("\n")
    print(f"\n📂 Test results successfully saved to: {log_path}")

if __name__ == "__main__":
    main()
