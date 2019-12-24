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


Images Resource
---------------

Since we are going to write and read image files, care needs to be taken of
making file I/O non-blocking. We'll give ``aiofiles`` a try::

  pip install aiofiles

We'll also need some basic configuration telling where to store our images.

In the ASGI flavour of Falcon, all responder methods, hooks and middleware
methods must be awaitable coroutines. With that in mind, let's go on to
implement the image collection resource:

.. code:: python

   # work in progress
