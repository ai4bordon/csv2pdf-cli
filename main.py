import argparse
import csv
import datetime
import os
import platform
import re
import subprocess
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, List, Tuple

from jinja2 import Template

# WeasyPrint выбран как простая библиотека для HTML→PDF, устанавливается через pip;
# при отсутствии системных зависимостей выводим подсказку и не продолжаем рендер.


class CliError(Exception):
    """Понятная ошибка для пользователя без трассбека."""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генерация PDF-чека из CSV и HTML-шаблона.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="data/input.csv",
        help="Путь к CSV с покупками (дефолт: data/input.csv).",
    )
    parser.add_argument(
        "-t",
        "--template",
        dest="template_path",
        default="templates/template.html",
        help="Путь к HTML-шаблону (дефолт: templates/template.html).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        default="output",
        help="Папка для сохранения PDF (дефолт: output).",
    )
    parser.add_argument(
        "--open",
        dest="auto_open",
        action="store_true",
        help="Открыть PDF после генерации системной командой.",
    )
    return parser.parse_args()


def detect_delimiter(sample: str) -> str:
    """Определяем разделитель из запятой или точки с запятой, иначе ошибка."""
    possible = [",", ";"]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(possible))
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = None
    if delimiter in possible:
        return delimiter
    raise CliError(
        "Не удалось определить разделитель CSV. Поддерживаются ',' или ';'. "
        "Проверьте файл или укажите корректный разделитель."
    )


def parse_price(raw: str) -> Decimal:
    """Парсинг цены с валидацией формата и неотрицательности."""
    text = (raw or "").strip()
    if not text:
        raise CliError("Цена не указана для одной из строк.")
    if "," in text and "." not in text:
        raise CliError("Цена должна использовать точку в качестве десятичного разделителя, не запятую.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise CliError(f"Некорректное значение цены: {text}")
    if value < 0:
        raise CliError(f"Цена не может быть отрицательной: {text}")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_qty(raw: str) -> int:
    """Парсинг количества с проверкой неотрицательности и целочисленности."""
    text = (raw or "").strip()
    if not text:
        raise CliError("Количество не указано для одной из строк.")
    if not text.isdigit():
        raise CliError(f"Количество должно быть неотрицательным целым: {text}")
    qty = int(text)
    return qty


def read_csv_rows(csv_path: Path) -> Tuple[List[dict], Decimal]:
    """Читает CSV, валидирует колонки и значения, возвращает позиции и итог."""
    if not csv_path.exists():
        raise CliError(f"Файл CSV не найден: {csv_path}")
    sample = csv_path.read_text(encoding="utf-8", errors="ignore")
    if not sample.strip():
        raise CliError("CSV пустой. Добавьте данные и повторите попытку.")
    delimiter = detect_delimiter(sample)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if not reader.fieldnames:
            raise CliError("В CSV отсутствует строка заголовков.")
        headers = {h.strip().lower() for h in reader.fieldnames}
        required = {"product", "price", "qty"}
        missing = required - headers
        if missing:
            raise CliError(f"В CSV отсутствуют обязательные колонки: {', '.join(sorted(missing))}")
        items = []
        total = Decimal("0.00")
        for row in reader:
            product = (row.get("product") or "").strip()
            if not product:
                raise CliError("Пустое значение товара в одной из строк.")
            price = parse_price(row.get("price", ""))
            qty = parse_qty(row.get("qty", ""))
            line_total = (price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total += line_total
            items.append(
                {
                    "product": product,
                    "price": f"{price:.2f}",
                    "qty": qty,
                    "line_total": f"{line_total:.2f}",
                }
            )
        if not items:
            raise CliError("CSV не содержит данных после заголовков.")
        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return items, total


def ensure_placeholders(template_text: str) -> None:
    """Проверяем наличие ключевых плейсхолдеров; допускаем точку перед именем."""
    required_names = ["product", "price", "qty", "total"]
    for name in required_names:
        pattern = re.compile(r"{{[^}]*\b(?:\w+\.)?" + re.escape(name) + r"\b[^}]*}}")
        if not pattern.search(template_text):
            raise CliError(
                f"В шаблоне отсутствует плейсхолдер для '{name}'. "
                "Добавьте его и повторите генерацию."
            )


def load_template(template_path: Path) -> Template:
    if not template_path.exists():
        raise CliError(f"Шаблон не найден: {template_path}")
    text = template_path.read_text(encoding="utf-8")
    ensure_placeholders(text)
    return Template(text)


def render_pdf(html_content: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"check_{timestamp}.pdf"
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise CliError(
            "Не удалось импортировать WeasyPrint. Убедитесь, что библиотека установлена и "
            "доступны системные зависимости (GTK/Pango/Cairo)."
        ) from exc
    try:
        HTML(string=html_content).write_pdf(str(output_path))
    except Exception as exc:
        raise CliError(
            "Рендер PDF не удался. Проверьте установку системных зависимостей WeasyPrint "
            "и корректность шаблона."
        ) from exc
    return output_path


def open_pdf(path: Path) -> None:
    """Открывает PDF системной командой, предупреждает при сбоях."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["xdg-open", str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print(
            "Предупреждение: не удалось открыть PDF автоматически. "
            f"Файл сохранен: {path}",
            flush=True,
        )


def build_html(template: Template, items: Iterable[dict], total: Decimal) -> str:
    """Готовим HTML из шаблона и данных."""
    return template.render(
        items=list(items),
        total=f"{total:.2f}",
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def main() -> None:
    args = parse_arguments()
    try:
        csv_path = Path(args.input)
        template_path = Path(args.template_path)
        output_dir = Path(args.output_dir)

        items, total = read_csv_rows(csv_path)
        template = load_template(template_path)
        html_content = build_html(template, items, total)
        pdf_path = render_pdf(html_content, output_dir)

        print(f"PDF успешно создан: {pdf_path}")
        if args.auto_open:
            open_pdf(pdf_path)
    except CliError as err:
        print(f"Ошибка: {err}", flush=True)
        raise SystemExit(1)
    except Exception as err:
        # Непредвиденные ошибки тоже без трассбека.
        print(f"Неожиданная ошибка: {err}", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
