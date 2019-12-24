Falcon ASGI Tutorial
====================

In this tutorial we'll try implementing an application for a simple image
sharing service, in the spirit of the
`(WSGI) Falcon "Look" Tutorial
<https://falcon.readthedocs.io/en/stable/user/tutorial.html>`_. Along the way,
we'll be alpha-testing the upcoming
`Falcon ASGI support
<https://gist.github.com/kgriffs/a719c84aa33069d8dcf98b925135da39>`_.


Disclaimer
----------

Needless to say, the recipes showcased below are **not production ready** (yet)
as this tutorial builds upon Falcon branches/PRs which are still undergoing
heavy development.


First Steps
-----------

Firstly, let's create a fresh environment and the corresponding project
directory structure, along the lines of
`First Steps from the WSGI tutorial
<https://falcon.readthedocs.io/en/stable/user/tutorial.html#first-steps>`_::

  asgilook
  ├── .venv
  └── asgilook
      ├── __init__.py
      └── app.py


.. note::
   Installing `virtualenv <https://docs.python-guide.org/dev/virtualenvs/>`_ is
   not needed for recent Python 3.x versions. We can simply create a
   *virtualenv* using the ``venv`` module from the standard library,
   for instance::

     python3.7 -m venv .venv

   However, the way above may be unavailable depending how Python is packaged
   and installed in your OS. FWIW, the
   `author of this document <https://github.com/vytas7>`_ finds it convenient
   to manage *virtualenv*\s with
   `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io>`_.

Next, we'll need to install the Falcon branch for ASGI::

  pip install git+https://github.com/kgriffs/falcon@asgi-final

An ASGI app skeleton (``app.py``) could look like:

.. code:: python

   import falcon.asgi

   app = falcon.asgi.App()


Hosting Our App
---------------

For running our application, we'll need an
`ASGI <https://asgi.readthedocs.io/>`_ server. Some of the popular choices
include:

* `Uvicorn <https://www.uvicorn.org/>`_
* `Daphne <https://github.com/django/daphne/>`_
* `Hypercorn <https://pgjones.gitlab.io/hypercorn/>`_

For a simple tutorial application like ours, any of the above should do.
Let's pick the popular ``uvicorn`` for now::

  pip install uvicorn

While at it, it might be handy to also install
`HTTPie <https://github.com/jakubroztocil/httpie>`_ HTTP client::

  pip install httpie


Now let's try loading our application::

  uvicorn asgilook.app:app
  INFO:     Started server process [2019]
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.

Let's verify it works by trying to access the URL provided above by
``uvicorn``::

  http http://127.0.0.1:8000
  HTTP/1.1 404 Not Found
  content-length: 0
  content-type: application/json
  date: Tue, 24 Dec 2019 13:37:01 GMT
  server: uvicorn

Woohoo, it works!!!

Well, sort of. Onwards to adding some real functionality!


Configuration
-------------

As in the WSGI "Look" tutorial, we are going to configure at least the storage
location. There are
`many approaches to handling application configuration
<https://falcon.readthedocs.io/en/stable/user/faq.html#what-is-the-recommended-approach-for-making-configuration-variables-available-to-multiple-resource-classes>`_;
here we'll just pass around a ``Config`` instance to resource initializers for
easier testing (coming later in this tutorial):

.. code:: python

    import os
    import uuid


    class Config:
        DEFAULT_CONFIG_PATH = '/tmp/asgilook'
        DEFAULT_UUID_GENERATOR = uuid.uuid4

        def __init__(self):
            self.storage_path = (os.environ.get('ASGI_LOOK_STORAGE_PATH')
                                 or self.DEFAULT_CONFIG_PATH)
            if not os.path.exists(self.storage_path):
                os.makedirs(self.storage_path)

            self.uuid_generator = Config.DEFAULT_UUID_GENERATOR


Image Store
-----------

Since we are going to read and write image files, care needs to be taken of
making file I/O non-blocking. We'll give ``aiofiles`` a try::

  pip install aiofiles

In addition, let's twist the original WSGI "Look" design a bit, and convert
all uploaded images to JPEG. Let's try the popular
`Pillow <https://pillow.readthedocs.io/>`_ library for that::

  pip install Pillow

We can now implement a basic async image store as:

.. code:: python

    import asyncio
    import datetime
    import io
    import os.path

    import aiofiles
    import falcon
    import PIL.Image


    class Image:

        def __init__(self, config, image_id, size):
            self.config = config
            self.image_id = image_id
            self.size = size
            self.modified = datetime.datetime.utcnow()

        @property
        def path(self):
            return os.path.join(self.config.storage_path, self.image_id)

        @property
        def uri(self):
            return f'/images/{self.image_id}.jpeg'

        def serialize(self):
            return {
                'id': self.image_id,
                'image': self.uri,
                'modified': falcon.dt_to_http(self.modified),
                'size': self.size,
            }


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

        def get(self, image_id):
            return self._images.get(image_id)

        def list_images(self):
            return sorted(self._images.values(), key=lambda item: item.modified)

        async def save(self, image_id, data):
            loop = asyncio.get_running_loop()
            image = await loop.run_in_executor(None, self._load_from_bytes, data)
            converted = await loop.run_in_executor(None, self._convert, image)

            path = os.path.join(self.config.storage_path, image_id)
            async with aiofiles.open(path, 'wb') as output:
                await output.write(converted)

            stored = Image(self.config, image_id, image.size)
            self._images[image_id] = stored
            return stored

Here we store data using ``aiofiles``, and run ``Pillow`` image transformation
functions in a threadpool executor, hoping that at least some of them release
the GIL during processing.


Images Resource(s)
------------------
In the ASGI flavour of Falcon, all responder methods, hooks and middleware
methods must be awaitable coroutines. With that in mind, let's go on to
implement the image collection, and the individual image resources:

.. code:: python

    import aiofiles
    import falcon


    class Images:

        def __init__(self, config, store):
            self.config = config
            self.store = store

        async def on_get(self, req, resp):
            resp.media = [image.serialize() for image in self.store.list_images()]

        async def on_get_image(self, req, resp, image_id):
            image = self.store.get(str(image_id))
            resp.stream = await aiofiles.open(image.path, 'rb')
            resp.content_type = falcon.MEDIA_JPEG

        async def on_post(self, req, resp):
            data = await req.stream.read()
            image_id = str(self.config.uuid_generator())
            image = await self.store.save(image_id, data)

            resp.location = image.uri
            resp.media = image.serialize()
            resp.status = falcon.HTTP_201

Here, note that we can directly assign an open ``aiofiles`` files to
``resp.stream``.


Running Our Application
-----------------------

Let's refactor our ``app.py`` to allow ``create_app()``\ing whenever we need
it, be it tests or the ASGI application module:

.. code:: python

    import falcon.asgi

    from .config import Config
    from .images import Images
    from .store import Store


    def create_app(config=None):
        config = config or Config()
        store = Store(config)
        images = Images(config, store)

        app = falcon.asgi.App()
        app.add_route('/images', images)
        app.add_route('/images/{image_id:uuid}.jpeg', images, suffix='image')

        return app

The ASGI application now resides in ``asgi.py``:

.. code:: python

    from .app import create_app

    app = create_app()


Running the application is not too dissimilar from the previous command line::

  uvicorn asgilook.asgi:app

Provided ``uvicorn`` is started as per the above command line, let's try
uploading some images::

  http POST localhost:8000/images @/home/user/Pictures/test.png

  HTTP/1.1 201 Created
  content-length: 173
  content-type: application/json
  date: Tue, 24 Dec 2019 17:32:18 GMT
  location: /images/5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c.jpeg
  server: uvicorn

  {
      "id": "5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c",
      "image": "/images/5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c.jpeg",
      "modified": "Tue, 24 Dec 2019 17:32:19 GMT",
      "size": [
          462,
          462
      ]
  }

Accessing the newly uploaded image::

  http localhost:8000/images/5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c.jpeg

  HTTP/1.1 200 OK
  content-type: image/jpeg
  date: Tue, 24 Dec 2019 17:34:53 GMT
  server: uvicorn
  transfer-encoding: chunked

  +-----------------------------------------+
  | NOTE: binary data not shown in terminal |
  +-----------------------------------------+

We could also open the link in the web browser to verify the converted JPEG
image looks as intended.

Let's check the image collection now::

  http localhost:8000/images

  HTTP/1.1 200 OK
  content-length: 175
  content-type: application/json
  date: Tue, 24 Dec 2019 17:36:31 GMT
  server: uvicorn

  [
      {
          "id": "5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c",
          "image": "/images/5cfd9fb6-259a-4c72-b8b0-5f4c35edcd3c.jpeg",
          "modified": "Tue, 24 Dec 2019 17:32:19 GMT",
          "size": [
              462,
              462
          ]
      }
  ]

The application file layout should now look like::

  asgilook
  ├── .venv
  └── asgilook
      ├── __init__.py
      ├── app.py
      ├── asgi.py
      ├── config.py
      ├── images.py
      └── store.py

In case you have any issues getting the things up and running, or just prefer
editing files to copy-pasting them, the file tree at this point of tutorial is
available in this repository as ``asgilook_v0.0.1``.


Dynamic Thumbnails
------------------

Let's pretend our image service customers want to render images in multiple
resolutions, for instance, for ``srcset`` for responsive HTML images or other
purposes.

Let's add a new method ``Store.make_thumbnail()`` to perform scaling on the
fly:

.. code:: python

    async def make_thumbnail(self, image, size):
        async with aiofiles.open(image.path, 'rb') as img_file:
            data = await img_file.read()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._resize, data, size)

As well as an internal helper to run the ``Pillow`` thumbnail operation that
is offloaded to a threadpool executor, again, in hoping that Pillow can release
the GIL for some operations:

.. code:: python

    def _resize(self, data, size):
        image = PIL.Image.open(io.BytesIO(data))
        image.thumbnail(size)

        resized = io.BytesIO()
        image.save(resized, 'JPEG')
        return resized.getvalue()

The ``store.Image`` class can be extended to also return URIs to thumbnails:

.. code:: python

    def thumbnails(self):
        def reductions(size, min_size):
            width, height = size
            factor = 2
            while width // factor >= min_size and height // factor >= min_size:
                yield (width // factor, height // factor)
                factor *= 2

        return [
            f'/thumbnails/{self.image_id}/{width}x{height}.jpeg'
            for width, height in reductions(
                self.size, self.config.min_thumb_size)]

Gluing everything together, such as adding a new route inside ``create_app``,
is left as an exercise for the reader.

The new ``thumbnails`` end-point should now render thumbnails on-the-fly::

  http POST localhost:8000/images @/home/user/Pictures/test.png
  HTTP/1.1 201 Created
  content-length: 319
  content-type: application/json
  date: Tue, 24 Dec 2019 18:58:20 GMT
  location: /images/f2375273-8049-4b10-b17e-8851db9ac7af.jpeg
  server: uvicorn

  {
      "id": "f2375273-8049-4b10-b17e-8851db9ac7af",
      "image": "/images/f2375273-8049-4b10-b17e-8851db9ac7af.jpeg",
      "modified": "Tue, 24 Dec 2019 18:58:21 GMT",
      "size": [
          462,
          462
      ],
      "thumbnails": [
          "/thumbnails/f2375273-8049-4b10-b17e-8851db9ac7af/231x231.jpeg",
          "/thumbnails/f2375273-8049-4b10-b17e-8851db9ac7af/115x115.jpeg"
      ]
  }


  http localhost:8000/thumbnails/f2375273-8049-4b10-b17e-8851db9ac7af/115x115.jpeg
  HTTP/1.1 200 OK
  content-length: 2985
  content-type: image/jpeg
  date: Tue, 24 Dec 2019 19:00:14 GMT
  server: uvicorn

  +-----------------------------------------+
  | NOTE: binary data not shown in terminal |
  +-----------------------------------------+

Again, we could also verify thumbnail URIs in the browser or image viewer that
supports HTTP input.


Caching Responses
-----------------

Although scaling thumbnails on-the-fly sounds cool and we also avoid many pesky
small files littering our storage, it also consumes CPU resources, and we would
soon find our application crumbling under load.

Let's thus implement response caching in Redis, utilizing
`aioredis <https://github.com/aio-libs/aioredis>`_ for async support::

  pip install aioredis

We will also need to serialize response data (the ``Content-Type`` header and
the body in the first version); ``msgpack`` should do::

  pip install msgpack

Our application will also need to access a Redis server. Apart from just
installing Redis server on your machine, one could also:

* Spin up Redis in Docker, eg::

    docker run -p 6379:6379 redis

* Considering Redis is installed on the machine, one could also try
  `pifpaf <https://github.com/jd/pifpaf>`_ for spinning up Redis just
  temporarily for ``uvicorn``::

    pifpaf run redis -- uvicorn asgilook.asgi:app

We are going to perform caching in Falcon Middleware. Again, note that all
middleware methods must be asynchronous. A simple cache (``cache.py``) could
look like:

.. code:: python

    import msgpack


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

        async def serialize_response(self, resp):
            data = await resp.render_body()
            return msgpack.packb([resp.content_type, data], use_bin_type=True)

        def deserialize_response(self, resp, data):
            resp.content_type, resp.data = msgpack.unpackb(data, raw=False)
            resp.complete = True
            resp.context.cached = True

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
                self.deserialize_response(resp, data)
                resp.set_header(self.CACHE_HEADER, 'Hit')
            else:
                resp.set_header(self.CACHE_HEADER, 'Miss')

        async def process_response(self, req, resp, resource, req_succeeded):
            if not req_succeeded:
                return

            key = f'{self.PREFIX}/{req.path}'

            if req.method in self.INVALIDATE_ON:
                await self.redis.delete(key)
            elif not resp.context.cached:
                data = await self.serialize_response(resp)
                await self.redis.set(key, data, expire=self.TTL)

Now, subsequent access to ``/thumbnails`` should be cached, as indicated by the
``x-asgilook-cache`` header::

  http localhost:8000/thumbnails/167308e4-e444-4ad9-88b2-c8751a4e37d4/115x115.jpeg
  HTTP/1.1 200 OK
  content-length: 2985
  content-type: image/jpeg
  date: Tue, 24 Dec 2019 19:46:51 GMT
  server: uvicorn
  x-asgilook-cache: Hit

  +-----------------------------------------+
  | NOTE: binary data not shown in terminal |
  +-----------------------------------------+

.. note::
   Left as another exercise for the reader: individual images are streamed
   directly from ``aiofiles`` instances, and caching therefore does not work
   for them at the moment.


Coming Up Soon
--------------

* Application testing
* Showcasing async hooks
