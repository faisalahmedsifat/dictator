
import json
from llama_cpp import Llama

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_browser",
            "description": "Open a web browser, optionally searching for a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the browser (e.g. chrome, firefox)", "default": "default"},
                    "search_query": {"type": "string", "description": "Text to search for"},
                    "url": {"type": "string", "description": "Direct URL to open"}
                },
                "required": ["search_query"]
            }
        }
    }
]

# 2. Mock Agent Function
def run_agent_demo():
    print("--- Loading Agent (Qwen 2.5 1.5B) ---")
    # Note: You need to download the GGUF model first!
    # model_path = "src/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    try:
        # Check if model exists, else placeholder
        llm = Llama(
            model_path="src/models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
            n_gpu_layers=-1, # Offload to GPU if available
            n_ctx=4096,
            verbose=False
        )
    except Exception as e:
        print(f"Model not found (Expected). Showing MOCK behavior for request.") 
        # Mocking the behavior for demonstration if model missing
        print("\nUser: 'Open Google Chrome and search Test test for me'")
        print("\n[Native Agent Logic]: Mapping to tool 'open_browser'...")
        
        # This is what the model WOULD output via grammar sampling:
        t_call = {
            "id": "call_123",
            "function": {
                "name": "open_browser",
                "arguments": '{"app_name": "google chrome", "search_query": "Test test"}'
            }
        }
        
        fn_name = t_call["function"]["name"]
        fn_args = json.loads(t_call["function"]["arguments"])
        
        print(f"\n[Agent Decided to Call Tool]: {fn_name}")
        print(f"Arguments: {fn_args}")
        return

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when needed."},
        {"role": "user", "content": "Open Google Chrome and search Test test for me."}
    ]


    print(f"\nUser: {messages[-1]['content']}")

    # 3. Call LLM with Tools
    # llama-cpp-python handles the grammar generation automatically!
    response = llm.create_chat_completion(
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    choice = response["choices"][0]["message"]
    
    # 4. Check for Tool Calls
    if "tool_calls" in choice:
        t_call = choice["tool_calls"][0]
        fn_name = t_call["function"]["name"]
        fn_args = json.loads(t_call["function"]["arguments"])
        
        print(f"\n[Agent Decided to Call Tool]: {fn_name}")
        print(f"Arguments: {fn_args}")
        
        # Mock Execution
        if fn_name == "get_weather":
            result = f"Weather in {fn_args.get('location')} is 28C, Sunny."
            print(f"Tool Output: {result}")
            
            # 5. Feed back to Agent
            messages.append(choice)
            messages.append({
                "role": "tool",
                "tool_call_id": t_call["id"],
                "content": result
            })
            
            final_response = llm.create_chat_completion(messages=messages)
            print(f"\nAgent Final Response: {final_response['choices'][0]['message']['content']}")
    else:
        print(f"Agent Response: {choice['content']}")

if __name__ == "__main__":
    run_agent_demo()
