"""Safe local chat façade; saved model choices do not imply installed adapters."""
from __future__ import annotations
from .storage import ProjectStore

def respond(store: ProjectStore, message: str) -> dict:
    if not isinstance(message,str) or not message.strip(): raise ValueError("message is required")
    if len(message) > 8000: raise ValueError("message must be 8,000 characters or fewer")
    settings=store.model_settings()
    if settings["adapter_available"]:
        answer=("Mock assistant active. I captured your request locally. Use the structured project draft to start the controlled engineering workflow. A real provider adapter is required before natural-language design analysis is available.")
    else:
        answer=(f"{settings['provider']} / {settings['model']} is saved as your preference, but no adapter is installed. No external request was made. Use the structured project draft or install a trusted provider adapter.")
    return {"role":"assistant","content":answer,"model_configuration":settings,"input_length":len(message)}
