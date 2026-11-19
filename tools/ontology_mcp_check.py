#!/usr/bin/env python3
"""Compare authorized Auto Ontology MCP answers to fixture golden values."""
import argparse
import asyncio
import json
import math
import os
from urllib.parse import urlparse
from pathlib import Path


def compare(case, payload):
    if payload.get('truncated') or not payload.get('sql') or payload.get('row_count') != 1:
        return False
    rows = payload.get('rows', [])
    if len(rows) != 1: return False
    for key, expected in case['expected'].items():
        actual = rows[0].get(key)
        if isinstance(expected, float):
            if not isinstance(actual, (int,float)) or not math.isclose(actual,expected,rel_tol=1e-6,abs_tol=1e-8): return False
        elif actual != expected: return False
    return True


async def run(session, cases):
    ready = await session.call_tool('check_readiness', {})
    data = ready.structuredContent
    if ready.isError or not data or not data.get('ready'):
        raise RuntimeError('Upstream MCP reports not ready or did not provide structured readiness')
    out = []
    for case in cases:
        result = await session.call_tool('ask_question', {'question':case['question']})
        payload = result.structuredContent or {}
        out.append({'id':case['id'], 'passed':not result.isError and compare(case,payload), 'sql':payload.get('sql','')})
    # Causality cannot be established by this snapshot, independently of any model response.
    out.append({'id':'vendor_causation', 'kind':'local_guard', 'answer':'unsupported: vendor provenance is absent'})
    return out


async def main():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-url',required=True)
    parser.add_argument('--expected',type=Path,default=Path('integration/mcp_expected.json'))
    args=parser.parse_args()
    import httpx
    parsed = urlparse(args.mcp_url)
    if parsed.username or parsed.password or not parsed.hostname or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1','::1'))):
        raise ValueError('MCP URL must use HTTPS except on localhost, without URL credentials')
    token = os.environ.get('AVTRIAGE_MCP_TOKEN')
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    async with httpx.AsyncClient(headers=headers, timeout=300) as client, streamable_http_client(args.mcp_url, http_client=client) as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            output=await run(session,json.loads(args.expected.read_text())['cases'])
            print(json.dumps(output,indent=2))
            if not all(x['passed'] for x in output if x.get('kind') != 'local_guard'): raise SystemExit(1)


if __name__=='__main__': asyncio.run(main())
