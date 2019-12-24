import asyncio
import datetime
import io
import os.path

import aiofiles
import PIL.Image


class Store:

    def __init__(self, config):
        self.config = config
        self._images = {}

    def _load_from_bytes(self, data):
        return PIL.Image.open(io.BytesIO(data))

    def _convert(self, image):
        rgb_image = image.convert('RGB')

        converted = io.BytesIO()
        rgb_image.save(converted, 'JPEG')
        return converted.getvalue()

    def list_images(self):
        return sorted(self._images.values(), key=lambda item: item['modified'])

    async def save(self, image_id, data):
        loop = asyncio.get_running_loop()
        image = await loop.run_in_executor(None, self._load_from_bytes, data)
        converted = await loop.run_in_executor(None, self._convert, image)

        path = os.path.join(self.config.storage_path, image_id)
        async with aiofiles.open(path, 'wb') as output:
            await output.write(converted)

        stored = {
            'id': image_id,
            'modified': datetime.datetime.utcnow().isoformat(),
            'size': image.size,
        }
        self._images[image_id] = stored
        return stored
