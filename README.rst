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

Needless to say, the showcased recipes are **not production ready** (yet) as
this tutorial builds upon Falcon branches/PRs which are still undergoing heavy
development.


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
   and installed in our OS. FWIW, the
   `author of this document <https://github.com/vytas7>`_ finds it convenient
   to manage *virtualenv*\s with
   `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io>`_.
