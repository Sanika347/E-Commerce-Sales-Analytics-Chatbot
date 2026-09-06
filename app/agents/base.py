from typing import Protocol, Dict, Any

class ILLMAgent(Protocol):
    async def query(self, user_text: str) -> Dict[str, Any]:
        """
        Takes a plain-English query and returns a dictionary containing:
        - chart_config: Chart.js configuration
        - insight: A one-sentence insight
        - raw_data: The JSON data from the tool
        - tool_calls: Info on what tool was called and with what parameters
        - error: (Optional) Any error message
        """
        pass
