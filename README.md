# Генератор PDF из CSV (CLI)

Минимальный CLI на Python 3.10+ для генерации PDF-чека из CSV с данными о покупках и HTML-шаблона.

## Установка и запуск 

```bash
# 1) Клонировать репозиторий
git clone https://github.com/ai4bordon/csv2pdf-cli.git
cd csv2pdf-cli

# 2) Создать и активировать venv
python -m venv venv
.\venv\Scripts\activate

# 3) Установить зависимости
pip install -r requirements.txt

# 4) Запустить генерацию (используются data/input.csv и templates/template.html)
python main.py
```

> Входной CSV-файл по умолчанию находится в каталоге `data` и должен называться `input.csv`.

## Кастомные пути и автооткрытие

```bash
python main.py --input data/input.csv --template templates/template.html --output-dir output --open
```

## Требования и зависимости

- Python 3.10+ (проверено на 3.11).
- Python-зависимости: `WeasyPrint`, `Jinja2` (устанавливаются из `requirements.txt`).
- Системные зависимости для WeasyPrint:
  - Windows: нужны Cairo, Pango, GDK-PixBuf (ставятся вместе с официальными сборками WeasyPrint для Windows; при ошибках установки устанавливайте эти компоненты из инструкции WeasyPrint).
  - Linux: GTK/Libpangocairo.
  - macOS: Pango/Cairo.

## Формат входных данных

- CSV в UTF-8 с разделителем `,` или `;`.
- Обязательные колонки: `product`, `price` (десятичная точка), `qty` (неотрицательное целое).

## Выход

- PDF сохраняется в `output/` под именем `check_YYYYMMDD_HHMMSS.pdf`.
- Флаг `--open` пытается открыть файл системной командой (`os.startfile` на Windows, `open` на macOS, `xdg-open` на Linux). При сбое генерация не отменяется — выводится предупреждение.
