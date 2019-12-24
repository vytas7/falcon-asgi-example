#!/usr/bin/env python

from setuptools import setup, find_packages


description = 'ASGI version of the Falcon "Look" tutorial.'

requirements = [
    'falcon @ git+https://github.com/kgriffs/falcon@asgi-final',
    'aiofiles>=0.4.0',
    'aioredis>=1.3.0',
    'msgpack',
    'Pillow>=6.0.0',
]

extras_require = {
    'dev': [
        'httpie',
        'uvicorn>=0.11.0',
    ],
    'test': [
        'birdisle',
        'pytest',
    ],
}

setup(
    name='falcon_asgi_example',
    version='0.0.3dev0',
    description=description,
    long_description=description,
    url='https://github.com/vytas7/falcon-asgi-example',
    author='Vytautas Liuolia',
    author_email='vytautas.liuolia@gmail.com',
    license='Apache v2',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='falcon asgi async cache redis uvicorn',
    packages=find_packages(exclude=['contrib', 'docs', 'test*']),
    python_requires='>=3.7',
    install_requires=requirements,
    extras_require=extras_require,
    package_data={},
    data_files=[],
)
