import uuid

import birdisle.aioredis
import falcon.asgi
import falcon.testing
import pytest

from asgilook.app import create_app
from asgilook.config import Config


@pytest.fixture()
def predictable_uuid():
    fixtures = (
        uuid.UUID('36562622-48e5-4a61-be67-e426b11821ed'),
        uuid.UUID('3bc731ac-8cd8-4f39-b6fe-1a195d3b4e74'),
        uuid.UUID('ba1c4951-73bc-45a4-a1f6-aa2b958dafa4'),
    )

    def uuid_func():
        try:
            return next(fixtures_it)
        except StopIteration:
            return uuid.uuid4()

    fixtures_it = iter(fixtures)
    return uuid_func


@pytest.fixture
def client(predictable_uuid):
    config = Config()
    config.create_redis_pool = birdisle.aioredis.create_redis_pool
    config.redis_host = None
    config.uuid_generator = predictable_uuid

    app = create_app(config)
    return falcon.testing.TestClient(app)
