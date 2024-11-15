# app/clients/openai_client.py

from openai import AsyncOpenAI
import threading


class OpenAI_Client:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config, secrets):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(OpenAI_Client, cls).__new__(cls)
                    cls._instance.initialize(config, secrets)
        return cls._instance

    def initialize(self, config, secrets):
        if not config or not isinstance(config, dict):
            raise ValueError("A valid configuration dictionary must be provided.")
        if not secrets or not isinstance(secrets, dict):
            raise ValueError("A valid secrets dictionary must be provided.")
        self.config = config["clients"]["openai"]
        api_key = secrets["openai_api_key"]
        self.client = AsyncOpenAI(api_key=api_key)

    def get_config(self):
        return self.config
