"""Real SDK chunk shapes, no external calls or patient data."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from openai.types.chat import ChatCompletionChunk
from web.backend.services import rag


def chunk(content=None, empty=False, reasoning=False):
    delta={'content':content}
    if reasoning:delta['reasoning_content']='private reasoning must not be shown'
    return ChatCompletionChunk(id='synthetic',created=0,model='synthetic',object='chat.completion.chunk',
        choices=[] if empty else [{'index':0,'delta':delta,'finish_reason':None}],
        usage={'prompt_tokens':5,'completion_tokens':3,'total_tokens':8} if empty else None)


@pytest.fixture
def client(monkeypatch):
    mock=Mock()
    monkeypatch.setattr(rag.openai,'OpenAI',lambda **kwargs:mock)
    monkeypatch.setattr(rag,'get_llm_config',lambda *args:{'provider':'dashscope','api_key':'synthetic','base_url':'https://synthetic','chat_model':'synthetic'})  # pragma: allowlist secret
    monkeypatch.setattr(rag,'_build_llm_messages',lambda *args:[{'role':'user','content':'synthetic'}])
    return mock


class Stream:
    def __init__(self,parts):self.parts=iter(parts);self.closed=False
    def __iter__(self):return self.parts
    def close(self):self.closed=True


def test_usage_chunks_before_between_and_after_text_do_not_interrupt_answer(client):
    stream=Stream([chunk(empty=True),chunk(reasoning=True),chunk('你'),chunk(empty=True),chunk('好'),chunk(),chunk(empty=True)])
    client.chat.completions.create.return_value=stream
    assert ''.join(rag.answer_question_stream('synthetic',[]))=='你好'
    assert stream.closed;client.close.assert_called_once()


def test_usage_only_stream_is_reported_as_empty_not_an_index_error(client):
    stream=Stream([chunk(empty=True),chunk()]);client.chat.completions.create.return_value=stream
    assert '暂未返回有效回答' in ''.join(rag.answer_question_stream('synthetic',[]))
    assert stream.closed


def test_cancelled_consumer_closes_upstream_stream(client):
    stream=Stream([chunk('第一个片段'),chunk('第二个片段')]);client.chat.completions.create.return_value=stream
    answer=rag.answer_question_stream('synthetic',[]);assert next(answer)=='第一个片段';answer.close()
    assert stream.closed;client.close.assert_called_once()


@pytest.mark.parametrize('response',[SimpleNamespace(choices=[]),SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])])
def test_nonstream_empty_response_is_recoverable(client,response):
    client.chat.completions.create.return_value=response
    assert '暂未返回有效回答' in rag.generate_answer('synthetic',[])
    client.close.assert_called_once()
