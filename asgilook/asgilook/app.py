import falcon.asgi

from .config import Config
from .images import Images
from .store import Store


def create_app():
    config = Config()
    store = Store(config)
    images = Images(store)

    app = falcon.asgi.App()
    app.add_route('/images', images)

    return app
