from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class ReplyState(TypedDict, total=False):
    conversation_id: str
    contact_id: str
    incoming_message: str
    intent: str | None
    message_count: int
    eligible_message_count: int
    eligible_character_count: int
    route: Literal['direct', 'rag']
    context: str
    sources: list[dict]
    suggestions: list[str]


class ReplyWorkflow:
    def __init__(self, store, generator, settings):
        self.store = store
        self.generator = generator
        self.settings = settings
        builder = StateGraph(ReplyState)
        builder.add_node('inspect_conversation', self._inspect)
        builder.add_node('direct_context', self._direct_context)
        builder.add_node('rag_context', self._rag_context)
        builder.add_node('generate_replies', self._generate)
        builder.add_edge(START, 'inspect_conversation')
        builder.add_conditional_edges(
            'inspect_conversation', self._route, {'direct': 'direct_context', 'rag': 'rag_context'}
        )
        builder.add_edge('direct_context', 'generate_replies')
        builder.add_edge('rag_context', 'generate_replies')
        builder.add_edge('generate_replies', END)
        self.graph = builder.compile()

    def _inspect(self, state: ReplyState) -> dict:
        stats = self.store.conversation_stats(state['conversation_id'], state['contact_id'])
        use_rag = (
            stats['eligible_message_count'] >= self.settings.rag_message_threshold
            or stats['eligible_character_count'] >= self.settings.rag_character_threshold
        )
        return {**stats, 'route': 'rag' if use_rag else 'direct'}

    @staticmethod
    def _route(state: ReplyState) -> Literal['direct', 'rag']:
        return state['route']

    def _direct_context(self, state: ReplyState) -> dict:
        rows = self.store.context_messages(
            state['conversation_id'], min(self.settings.direct_context_messages, self.settings.rag_message_threshold)
        )
        return {'context': self._format_messages(rows), 'sources': []}

    def _rag_context(self, state: ReplyState) -> dict:
        self.store.ensure_index(state['conversation_id'], state['contact_id'])
        retrieved = self.store.retrieve(
            state['contact_id'], state['conversation_id'], state['incoming_message'], self.settings.rag_top_k,
            ensure_index=False,
        )
        recent = self.store.context_messages(state['conversation_id'], self.settings.rag_recent_messages)
        context = 'Recent messages:\n' + self._format_messages(recent)
        if retrieved['results']:
            context += '\n\nRelevant older messages:\n' + '\n\n'.join(item['text'] for item in retrieved['results'])
        sources = [
            {'chunk_id': item['chunk_id'], 'score': item['score'], 'message_ids': [s['id'] for s in item['sources']]}
            for item in retrieved['results']
        ]
        return {'context': context, 'sources': sources}

    @staticmethod
    def _format_messages(rows: list[dict]) -> str:
        return '\n'.join(f"{row['role']}: {row['text']}" for row in rows)

    def _generate(self, state: ReplyState) -> dict:
        return {'suggestions': self.generator.generate(state['context'], state['incoming_message'], state.get('intent'))}

    def invoke(self, conversation_id: str, contact_id: str, incoming_message: str, intent: str | None) -> dict:
        result = self.graph.invoke({
            'conversation_id': conversation_id,
            'contact_id': contact_id,
            'incoming_message': incoming_message,
            'intent': intent,
        })
        return {
            'route': result['route'],
            'message_count': result['message_count'],
            'eligible_message_count': result['eligible_message_count'],
            'eligible_character_count': result['eligible_character_count'],
            'suggestions': result['suggestions'],
            'sources': result['sources'],
        }
