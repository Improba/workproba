"""Fixtures réponses Mistral Conversations (web_search)."""

MISTRAL_WEB_SEARCH_RESPONSE = {
    "conversation_id": "conv_test",
    "outputs": [
        {
            "type": "tool.execution",
            "name": "web_search",
            "object": "entry",
            "id": "tool_exec_test",
        },
        {
            "type": "message.output",
            "content": [
                {
                    "type": "text",
                    "text": "The last winner of the European Football Cup was Spain",
                },
                {
                    "type": "tool_reference",
                    "tool": "web_search",
                    "title": "UEFA Euro Winners List",
                    "url": "https://www.example.com/winners.html",
                    "source": "brave",
                },
                {
                    "type": "tool_reference",
                    "tool": "web_search",
                    "title": "UEFA Euro winners: Know the champions",
                    "url": "https://www.olympics.com/en/news/uefa-winners",
                    "source": "brave",
                },
                {"type": "text", "text": "."},
            ],
            "object": "entry",
            "id": "msg_test",
            "model": "mistral-medium-latest",
            "role": "assistant",
        },
    ],
    "usage": {
        "prompt_tokens": 188,
        "completion_tokens": 55,
        "total_tokens": 7355,
        "connector_tokens": 7112,
        "connectors": {"web_search": 1},
    },
    "object": "conversation.response",
}
