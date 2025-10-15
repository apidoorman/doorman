import os

from utils.constants import Defaults

def max_page_size() -> int:
    try:
        env = os.getenv(Defaults.MAX_PAGE_SIZE_ENV)
        if env is None or str(env).strip() == '':
            return Defaults.MAX_PAGE_SIZE_DEFAULT
        return max(int(env), 1)
    except Exception:
        return Defaults.MAX_PAGE_SIZE_DEFAULT

def validate_page_params(page: int, page_size: int) -> tuple[int, int]:
    p = int(page)
    ps = int(page_size)
    if p < 1:
        raise ValueError('page must be >= 1')
    m = max_page_size()
    if ps < 1:
        raise ValueError('page_size must be >= 1')
    if ps > m:
        raise ValueError(f'page_size must be <= {m}')
    return p, ps

