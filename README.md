Exe.шник знаходиться у теці dist/

Структура програми:
dist /
    main.exe
    icon.ico
    maps/
        ***.asc
    templates/
        ***.txt
        hide_tab_dont_delete_template_folder/
            ***.txt

----------

Для власного редагування, треба мати python 3.12

Локальне середовище. Щоб створити, в консолі переходимо до теки проєкту:

cd C:\Path\to\folder\topo

Та створюємо командою:

python -m venv venv

після чого середовище необхідно активувати:

.\venv\Scripts\activate

Залежності прописані у файлі requirements.txt й їх треба спершу встановити:

python -m pip install --upgrade pip 
pip install -r requirements.txt

Коли все завантажиться, можна запускати програму командою:

python main.py

Для дебагу виключно математичної складової можна використовувати:

python maths.py


Коли є потреба створити новий .exe, ось команда:
pyinstaller --onefile --hidden-import maths --hidden-import mgrs --add-binary venv\Lib\site-packages\libmgrs.cp312-win_amd64.pyd:. --icon=icon.ico main.py

Він автоматично з'являється в теці dist, але спокійно може працювати далі й за її межами, головне щоб був доступ до мап

-----------

Карти зберігати у відповідній теці, рахуються тільки файли формату .asc. 
Шаблони мають формат .txt - легше задавати при створенні у самій програмі, 
але можна редагувати вручну, дотримуючись формату:

Назва параметру: а, б, в, г

Де а - значення за змовчуванням, б - мінімальне допустиме значення, в - максимум, г - крок точності.

У разі створення нових параметрів, що використовуються для математики, 
їх також варто прописати у глобальній змінній DEFAULT_TAB_SETTINGS
Інші глобальні змінні, що можна редагувати:
MAPS_FOLDER = "maps/"
TEMPLATES_FOLDER = "templates/"
SAVE_COLUMNS = 5 -- кількість колонок в інтерфейсі під мапою

-----------

Загальна структура проєкту:
topo/
    pycache/
    venv/
    dist/ 	- тут формується .exe
    maps/
        ***.asc
    templates/
        ***.txt
        hide_tab_dont_delete_template_folder/
            ***.txt
    main.py 	- основний цикл програми
    maths.py	- математичні функції
    icon.ico
    main.spec	- параметри для .exe
    pyqt.ui	- легасі xml рендер UI 
    output.py	- та його конвертація в python
    notes.py	- просто чернетка, можна видаляти
    requirements.txt
    readme.txt
