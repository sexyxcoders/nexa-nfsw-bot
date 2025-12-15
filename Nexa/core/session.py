import aiohttp

_session = None

async def get_session():
    global _session
    if not _session or _session.closed:
        _session = aiohttp.ClientSession()
    return _session