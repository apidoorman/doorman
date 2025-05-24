from datetime import datetime, timedelta
import heapq

jwt_blacklist = {}

class TimedHeap:
    def __init__(self, purge_after=timedelta(hours=1)):
        self.heap = []
        self.purge_after = purge_after

    async def push(self, item):
        expire_time = datetime.now() + self.purge_after
        heapq.heappush(self.heap, (expire_time, item))

    async def pop(self):
        await self.purge()
        if self.heap:
            return heapq.heappop(self.heap)[1]
        raise IndexError("pop from an empty priority queue")

    async def purge(self):
        current_time = datetime.now()
        while self.heap and self.heap[0][0] < current_time:
            heapq.heappop(self.heap)

    async def peek(self):
        await self.purge()
        if self.heap:
            return self.heap[0][1]
        return None

async def purge_expired_tokens():
    for key, timed_heap in list(jwt_blacklist.items()):
        await timed_heap.purge()
        if not timed_heap.heap:
            del jwt_blacklist[key]