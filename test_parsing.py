
import json
from src.agent import process_command

# Mock Llama to avoid loading model
import src.agent
class MockChoice:
    def __init__(self, content):
        self.content = content
    def get(self, key, default=None):
        return [] # no tool_calls

class MockResponse:
    def __init__(self, content):
        self.choices = [{"message": {"content": content, "tool_calls": []}}]
    def __getitem__(self, key):
        return self.choices

class MockLLM:
    def create_chat_completion(self, messages, tools, tool_choice):
        # Simulate Qwen output from logs
        return {
            "choices": [{
                "message": {
                    "content": '<tool_call>\n{{"name": "open_browser", "arguments": {"app_name": "chrome", "search_query": "browser width"}}\n</tool_call>',
                    "tool_calls": []
                }
            }]
        }

src.agent.llm = MockLLM()

print("Running parsing test...")
process_command("test")
