import logging
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_global_logging_middleware_404():
    from doorman import doorman
    import logging
    
    # Custom handler to capture logs
    class ListHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(self.format(record))
            
    logger = logging.getLogger('doorman.gateway')
    handler = ListHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        async with AsyncClient(app=doorman, base_url='http://testserver') as ac:
            path = '/some/random/path/that/does/not/exist'
            r = await ac.get(path)
            assert r.status_code == 404
            
            # Verify log entry exists in captured records
            log_text = '\n'.join(handler.records)
            assert 'status_code: 404' in log_text
            assert path in log_text
    finally:
        logger.removeHandler(handler)

