import uuid

import falcon


class Images:

    def __init__(self, store):
        self.store = store

    async def on_get(self, req, resp):
        resp.media = self.store.list_images()

    async def on_post(self, req, resp):
        data = await req.stream.read()
        image_id = str(uuid.uuid4())

        resp.status = falcon.HTTP_201
        resp.media = await self.store.save(image_id, data)
        resp.location = f'/images/{image_id}.jpeg'
