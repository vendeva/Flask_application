##### CLI
#### Установить в PyCharm плагины для работы с env файлами
#### Добавить env файл в корень проекта с содержанием:
* PYTHONPATH="./src"
* FLASK_APP="./src/app:create_app"

#### Cоздадим виртуальное окружение в папке проекта:
* `py -m virtualenv .venv`


#### Активируем виртуальное окружение:
* Set-ExecutionPolicy Unrestricted -Force - если есть проблемы с актиацией на Windows
* `\.venv\Scripts\activate`


#### Указать рабочую папку проекта в PyCharm это:
* Settings -> Project -> Project Structure

#### Выбрать интерпретатор python:
* Settings -> Project -> Project Interpreter
* `.venv\Scripts\python.exe`

#### Запустить приложение Flask:
* Edit configuration в панели Pycharm
* target: app
* application: create_app
* FLASK_ENV: development
* FLASK_DEBUG отметить галочку
* интерпретатор должен быть `.venv\Scripts\python.exe`
* В терминале Python убить приложение и перезапустить из Pycharm.




