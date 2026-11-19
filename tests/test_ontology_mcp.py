import asyncio
from types import SimpleNamespace
from tools.ontology_mcp_check import compare, run


def test_fixture_transport_and_guard():
    case={'id':'n','question':'count','expected':{'n':1}}
    class Fake:
        async def call_tool(self, name, args):
            if name == 'check_readiness': return SimpleNamespace(isError=False, structuredContent={'ready':True})
            return SimpleNamespace(isError=False, structuredContent={'sql':'SELECT 1 AS n','row_count':1,'rows':[{'n':1}],'truncated':False})
    out=asyncio.run(run(Fake(),[case]))
    assert out[0]['passed'] and out[1]['kind'] == 'local_guard'
    assert 'unsupported' in out[-1]['answer']
    assert not compare(case,{'sql':'','row_count':1,'rows':[{'n':1}]})
