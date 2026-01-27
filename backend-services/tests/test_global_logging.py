import logging
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_global_logging_middleware_404(capsys):
    from doorman import doorman
    import logging
    # Ensure level is INFO
    logging.getLogger('doorman.gateway').setLevel(logging.INFO)
    
    async with AsyncClient(app=doorman, base_url='http://testserver') as ac:
        path = '/some/random/path/that/does/not/exist'
        r = await ac.get(path)
        assert r.status_code == 404
        
        captured = capsys.readouterr()
        # Verify log entry exists in stdout/stderr
        assert 'status_code: 404' in captured.out or 'status_code: 404' in captured.err, f"Log not found in output: {captured}"
        assert path in captured.out or path in captured.err

