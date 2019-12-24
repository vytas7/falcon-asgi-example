class RedisCache:
    PREFIX = 'asgilook:'
    INVALIDATE_ON = frozenset({'DELETE', 'POST', 'PUT'})
    CACHE_HEADER = 'X-ASGILook-Cache'
    TTL = 3600

    def __init__(self, config):
        self.config = config

        # TODO(vytas): create_redis_pool() is a coroutine, how to run that
        # inside __init__()?
        self.redis = None

    async def create_pool(self):
        self.redis = await self.config.create_redis_pool(
            self.config.redis_host)

    async def process_request(self, req, resp):
        resp.context.cached = False

        if req.method in self.INVALIDATE_ON:
            return

        if self.redis is None:
            await self.create_pool()

        key = f'{self.PREFIX}/{req.path}'
        data = await self.redis.get(key)
        if data is not None:
            resp.complete = True
            resp.context.cached = True
            resp.data = data
            resp.set_header(self.CACHE_HEADER, 'Hit')
        else:
            resp.set_header(self.CACHE_HEADER, 'Miss')

    async def process_response(self, req, resp, resource, req_succeeded):
        if not req_succeeded:
            return

        key = f'{self.PREFIX}/{req.path}'

        if req.method in self.INVALIDATE_ON:
            await self.redis.delete(key)
        elif not resp.context.cached and resp.data:
            await self.redis.set(key, resp.data, expire=self.TTL)
