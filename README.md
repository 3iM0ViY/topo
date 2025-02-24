# Документація проєкту

### Розташування виконуваного файлу

Exe.шник знаходиться у теці `dist/` в релізі.

Структура програми:
```
dist/
    main.exe
    icon.ico
    maps/
        ***.asc
    templates/
        ***.txt
        hide_tab_dont_delete_template_folder/
            ***.txt
```

----------

### Необхідні інструменти

Для власного редагування програми необхідно мати **Python 3.12**.

### Налаштування локального середовища

1. Щоб створити, в консолі переходимо до теки проєкту:
   ```bash
   cd C:\Path\to\folder\topo
2. Створення віртуального середовища:

    ```bash
    python -m venv venv

3. Активація:
   ```bash
    .\venv\Scripts\activate

4. Залежності прописані у файлі `requirements.txt` й їх треба встановити:
    ```bash
    python -m pip install --upgrade pip 
    pip install -r requirements.txt


## Запуск програми

Для запуску пайтон версії програми, використовувати команду:

    python main.py
    
### Дебаг математичної частини
Для дебагу виключно математичної складової можна використовувати:

    python maths.py

## Створення нового `.exe`
Коли є потреба створити новий .exe, ось команда:
```
pyinstaller --onefile --hidden-import maths --hidden-import mgrs --add-binary venv\Lib\site-packages\libmgrs.cp312-win_amd64.pyd:. --icon=icon.ico main.py
```
Виконуваний файл автоматично з’явиться у теці dist/. Його можна перенести в інші теки, головне — забезпечити доступ до мап.

## Формат карт і шаблонів

### Карти
Зберігайте карти у теці `maps/`. Підтримуються лише файли формату `.asc`.
### Шаблони
Шаблони мають формат `.txt` - легше задавати при створенні у самій програмі, 
але можна редагувати вручну, дотримуючись формату:

`Назва параметру: а, б, в, г`

Де 
 - а - значення за змовчуванням
 - б - мінімальне допустиме значення
 - в - максимум 
 - г - крок точності

У разі створення нових параметрів, що використовуються для математики,  їх також варто прописати у глобальній змінній `DEFAULT_TAB_SETTINGS`.

## Глобальні змінні
 - `DEFAULT_TAB_SETTINGS = {...}` - словник з форматом налаштувань, котрі враховує програма
 - `MAPS_FOLDER = "maps/"` - тека, де розташовуються ASCII мапи
 - `TEMPLATES_FOLDER = "templates/"` - тека, де розташовуються заготовлені шаблони налаштувань засобів
 - `SAVE_COLUMNS = 5` - кількість колонок в інтерфейсі під мапою

## Загальна структура проєкту:
```
topo/
    pycache/
    venv/
    dist/              # тут формується .exe
    maps/
        ***.asc
    templates/
        ***.txt
        hide_tab_dont_delete_template_folder/
            ***.txt
    main.py            # основний цикл програми
    maths.py           # математичні функції
    icon.ico
    main.spec          # параметри для .exe
    pyqt.ui            # легасі xml рендер UI
    output.py          # конвертація UI в Python
    notes.py           # чернетка, можна видаляти
    requirements.txt
    readme.txt
```

# Ілюстрації
![зображення_2025-02-24_130328266](https://github.com/user-attachments/assets/ee3a0248-4dcc-4f88-aa98-8b6312c0cec9)
<img src="https://github.com/user-attachments/assets/b0731ab4-d0f9-4803-8630-712812a0d256" height="300" >
<img src="https://github.com/user-attachments/assets/8a221e8d-b466-4471-8319-48f9fbcd6660" height="300">


