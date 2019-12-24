import os


class Config:

    def __init__(self):
        self.storage_path = (os.environ.get('ASGI_LOOK_STORAGE_PATH')
                             or '/tmp/asgilook')

        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
