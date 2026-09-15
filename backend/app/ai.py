import json

from openai import OpenAI

from .parser import ImportProblem


class OpenAIReplyGenerator:
    def __init__(self, api_key: str | None, model: str):
        self.model = model
        self.client = OpenAI(api_key=api_key) if api_key else None

    @property
    def configured(self) -> bool:
        return self.client is not None

    def generate(self, context: str, incoming_message: str, intent: str | None) -> list[str]:
        if self.client is None:
            raise ImportProblem(
                'openai_not_configured',
                'Set OPENAI_API_KEY in backend/.env, restart the backend, and try again.',
                503,
            )
        instructions = (
            'You draft personal chat replies. Use only the supplied conversation context. '
            'Do not invent shared history. Preserve the relationship tone and emoji style when the context supports it. '
            'Return JSON only: an object with a suggestions array containing exactly three distinct reply strings. '
            'Each suggestion must be ready to send and no longer than 400 characters.'
        )
        request = {
            'incoming_message': incoming_message,
            'intent': intent or 'Respond naturally',
            'conversation_context': context,
        }
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=json.dumps(request, ensure_ascii=False),
            store=False,
            text={'format': {
                'type': 'json_schema',
                'name': 'reply_suggestions',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'properties': {
                        'suggestions': {
                            'type': 'array',
                            'minItems': 3,
                            'maxItems': 3,
                            'items': {'type': 'string', 'minLength': 1, 'maxLength': 400},
                        }
                    },
                    'required': ['suggestions'],
                    'additionalProperties': False,
                },
            }},
        )
        try:
            payload = json.loads(response.output_text)
            suggestions = payload['suggestions']
            if not isinstance(suggestions, list) or len(suggestions) != 3:
                raise ValueError
            cleaned = [str(item).strip() for item in suggestions]
            if any(not item or len(item) > 400 for item in cleaned) or len(set(cleaned)) != 3:
                raise ValueError
            return cleaned
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError('The model returned an invalid reply-suggestion format.') from exc
