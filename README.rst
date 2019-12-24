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
GIL during processing.


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


Running the application is not too dissimilar to the previous command line::

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
