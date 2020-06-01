import os


class Config:
    DB_CONNECTION = os.getenv('DB_CONNECTION', 'db2.sqlite')
    SECRET_KEY = os.getenv('SECRET_KEY', 'secret').encode()
    JSON_SORT_KEYS = False
    UPLOAD_FOLDER = 'images'
    ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
