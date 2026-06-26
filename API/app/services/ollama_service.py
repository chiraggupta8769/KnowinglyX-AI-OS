from ollama import Client


class OllamaService:
    def __init__(self):
        self.client = Client(host="http://127.0.0.1:11434")

    def chat(self, prompt: str, model: str = "gemma3:4b"):
        response = self.client.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]


ollama_service = OllamaService()