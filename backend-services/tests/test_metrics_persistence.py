import pytest


@pytest.mark.asyncio
async def test_metrics_persist_and_restore(tmp_path, authed_client):
    r1 = await authed_client.get('/api/status')
    r2 = await authed_client.get('/api/status')
    assert r1.status_code == 200 and r2.status_code == 200

    from utils.metrics_util import metrics_store

    before = metrics_store.to_dict()
    assert before.get('total_requests', 0) >= 1

    path = tmp_path / 'metrics.json'
    metrics_store.save_to_file(str(path))
    assert path.exists() and path.stat().st_size > 0

    metrics_store.load_dict({})
    zeroed = metrics_store.to_dict()
    assert zeroed.get('total_requests', 0) == 0
    assert zeroed.get('total_bytes_in', 0) == 0
    assert zeroed.get('total_bytes_out', 0) == 0

    metrics_store.load_from_file(str(path))
    after = metrics_store.to_dict()

    def _normalize(d):
        def _norm_bucket(b):
            b2 = dict(b)
            if isinstance(b2.get('status_counts'), dict):
                b2['status_counts'] = {str(k): v for k, v in b2['status_counts'].items()}
            return b2

        out = dict(d)
        if isinstance(out.get('status_counts'), dict):
            out['status_counts'] = {str(k): v for k, v in out['status_counts'].items()}
        if isinstance(out.get('buckets'), list):
            out['buckets'] = [_norm_bucket(b) for b in out['buckets']]
        return out

    assert _normalize(after) == _normalize(before)
