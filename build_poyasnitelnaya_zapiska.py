from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

import project


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
RAW_DIR = BASE_DIR / "data" / "raw" / "3w"
CM_IMAGE_PATH = REPORTS_DIR / "confusion_matrix.png"
CLASS_DIST_IMAGE_PATH = REPORTS_DIR / "class_distribution.png"
OUTPUT_DOCX_PATH = REPORTS_DIR / "Пояснительная_записка_3W.docx"


def setup_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)


def setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    p_format = normal.paragraph_format
    p_format.line_spacing = 1.5
    p_format.first_line_indent = Cm(1.25)
    p_format.space_before = Pt(0)
    p_format.space_after = Pt(0)
    p_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "

    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")

    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)


def setup_footer_with_page_number(doc: Document) -> None:
    footer = doc.sections[0].footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    add_page_number(paragraph)


def add_heading_center(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.name = "Times New Roman"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        run.font.size = Pt(14)
        run.bold = True


def add_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_code_block(doc: Document, code: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing = 1.0
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(code)
    run.font.name = "Courier New"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Courier New")
    run.font.size = Pt(10)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)


def extract_function_source(file_path: Path, func_name: str) -> str:
    if not file_path.exists():
        return f"# File not found: {file_path}"
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(
        rf"^def\s+{re.escape(func_name)}\s*\(.*?(?=^def\s+\w+\s*\(|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return f"# Function not found: {func_name} in {file_path.name}"
    return m.group(0).strip() + "\n"


def class_file_counts() -> dict[int, int]:
    counts: dict[int, int] = {}
    if not RAW_DIR.exists():
        return counts
    for d in RAW_DIR.iterdir():
        if d.is_dir() and d.name.isdigit():
            counts[int(d.name)] = len(list(d.glob("*.csv")))
    return dict(sorted(counts.items()))


def parse_metrics() -> tuple[str, str]:
    report_path = REPORTS_DIR / "classification_report.txt"
    if not report_path.exists():
        return "N/A", "N/A"
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    macro = re.search(r"Macro F1:\s*([0-9.]+)", text)
    weighted = re.search(r"Weighted F1:\s*([0-9.]+)", text)
    return (
        macro.group(1) if macro else "N/A",
        weighted.group(1) if weighted else "N/A",
    )


def build_class_distribution_plot(counts: dict[int, int]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    xs = list(counts.keys())
    ys = list(counts.values())
    plt.figure(figsize=(10, 5))
    plt.bar(xs, ys)
    plt.title("Raspredelenie primerov po klassam 3W")
    plt.xlabel("Klass")
    plt.ylabel("Kolichestvo CSV failov")
    plt.tight_layout()
    plt.savefig(CLASS_DIST_IMAGE_PATH, dpi=200)
    plt.close()


def add_title_page(doc: Document) -> None:
    p = doc.add_paragraph(
        "Министерство науки и высшего образования Российской Федерации\n"
        "_______________________________________________\n"
        "_______________________________________________"
    )
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)

    doc.add_paragraph()
    p2 = doc.add_paragraph("ПОЯСНИТЕЛЬНАЯ ЗАПИСКА")
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.runs[0].bold = True
    p2.runs[0].font.size = Pt(16)

    p3 = doc.add_paragraph(
        "к учебному проекту по дисциплине «Искусственный интеллект»\n"
        "на тему:\n"
        "«Распознавание нештатных событий на нефтегазовой скважине\n"
        "по данным датчиков на основе датасета 3W»"
    )
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.first_line_indent = Cm(0)

    for _ in range(8):
        doc.add_paragraph()

    p4 = doc.add_paragraph(
        "Выполнил: студент __________________________\n"
        "Группа: _________________________________\n"
        "Проверил: _______________________________"
    )
    p4.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p4.paragraph_format.first_line_indent = Cm(0)

    for _ in range(5):
        doc.add_paragraph()

    p5 = doc.add_paragraph("2026")
    p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p5.paragraph_format.first_line_indent = Cm(0)

    doc.add_page_break()


def add_abbreviations(doc: Document) -> None:
    add_heading_center(doc, "СПИСОК СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ", level=1)
    add_paragraph(
        doc,
        "В работе используются общепринятые сокращения нефтегазовой отрасли и машинного "
        "обучения. Для обеспечения однозначной интерпретации результатов ниже приведены "
        "основные сокращения, применяемые в тексте."
    )
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Сокращение"
    table.rows[0].cells[1].text = "Расшифровка"

    rows = [
        ("ИИ", "Искусственный интеллект"),
        ("ML", "Machine Learning, машинное обучение"),
        ("3W", "Petrobras 3W Dataset for Well Undesirable Events"),
        ("BSW", "Basic Sediment and Water, показатель обводненности"),
        ("DHSV", "Downhole Safety Valve, подземный предохранительный клапан"),
        ("PCK", "Элемент дросселирования/контрольный узел потока"),
        ("SCADA", "Система диспетчерского контроля и сбора данных"),
        ("F1-score", "Гармоническое среднее precision и recall"),
    ]
    for short, full in rows:
        c = table.add_row().cells
        c[0].text = short
        c[1].text = full
    doc.add_page_break()


def add_introduction(doc: Document) -> None:
    add_heading_center(doc, "ВВЕДЕНИЕ", level=1)
    add_paragraph(
        doc,
        "Современные нефтегазовые скважины эксплуатируются в условиях высокой динамики "
        "технологических параметров, где оперативное выявление нештатных режимов оказывает "
        "прямое влияние на безопасность, экономическую эффективность и ресурс оборудования. "
        "Традиционный подход, основанный исключительно на экспертном контроле трендов, "
        "затруднен из-за большого объема телеметрии и необходимости быстрого принятия решений."
    )
    add_paragraph(
        doc,
        "Целью настоящей работы является разработка и апробация программного решения на базе "
        "методов машинного обучения для автоматизированной классификации состояний скважины "
        "по временным рядам датчиков. В качестве основы выбран датасет 3W, содержащий как "
        "нормальные режимы, так и различные типы нежелательных событий."
    )
    add_paragraph(
        doc,
        "Практическая значимость проекта состоит в создании готового к демонстрации прототипа, "
        "который включает этапы подготовки данных, обучения модели, интерпретации результата и "
        "пользовательского интерфейса для загрузки новых файлов. Результаты оформлены в виде "
        "модели, графических материалов и текстовых отчетов, пригодных для учебной защиты."
    )


def add_theory(doc: Document) -> None:
    add_heading_center(doc, "1 Теоретические основы задачи", level=1)
    add_paragraph(
        doc,
        "Задача, рассматриваемая в проекте, относится к области многоклассовой классификации "
        "временных рядов. Исходные данные представлены последовательностями измерений давления, "
        "температуры и расхода газа. Для каждого эпизода наблюдения требуется определить класс "
        "состояния: нормальный режим или конкретный тип нежелательного события."
    )
    add_paragraph(
        doc,
        "В инженерной постановке целевая функция системы состоит в раннем обнаружении изменений "
        "поведения потока и оборудования. Для этого применяются статистические признаки, "
        "характеризующие уровень сигнала, вариативность, асимметрию по квантилям и динамику "
        "тренда. Такие признаки позволяют перейти от длинного временного ряда к компактному "
        "вектору, пригодному для классических алгоритмов машинного обучения."
    )
    add_paragraph(
        doc,
        "В качестве базовой модели выбран ансамблевый алгоритм Random Forest. Он устойчив к "
        "шуму, способен работать с нелинейными зависимостями и не требует сложной предварительной "
        "нормализации данных. Для инженерных данных, содержащих пропуски и разнородные диапазоны, "
        "данный подход является практичным и интерпретируемым для учебного проекта."
    )


def add_dataset_section(doc: Document, counts: dict[int, int]) -> None:
    add_heading_center(doc, "2 Датасет и подготовка данных", level=1)
    total = sum(counts.values())
    add_paragraph(
        doc,
        f"В работе использован открытый датасет 3W. В локальной копии проекта содержится {total} "
        f"CSV-файлов, распределенных по девяти классам (от 0 до 8). Каждый CSV-файл представляет "
        "собой отдельный эпизод наблюдения за состоянием скважины."
    )
    add_paragraph(
        doc,
        "Базовые входные признаки включают временную метку и сигналы датчиков: P-PDG, P-TPT, "
        "T-TPT, P-MON-CKP, T-JUS-CKP, P-JUS-CKGL, T-JUS-CKGL, QGL. В исходных файлах также "
        "присутствует колонка class, используемая как целевая метка в режиме обучения."
    )

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Класс"
    table.rows[0].cells[1].text = "Название"
    table.rows[0].cells[2].text = "Интерпретация"
    table.rows[0].cells[3].text = "Количество CSV"

    for cls, cnt in counts.items():
        row = table.add_row().cells
        row[0].text = str(cls)
        row[1].text = project.class_name(cls)
        row[2].text = project.class_description(cls)
        row[3].text = str(cnt)

    add_paragraph(
        doc,
        "На этапе предобработки выполнена очистка аномальных значений. Числа с чрезмерно большим "
        "модулем исключаются, бесконечные значения заменяются на NaN, после чего на этапе обучения "
        "применяется медианная импутация. Данный подход обеспечивает устойчивость модели к "
        "неполноте телеметрии."
    )

    if CLASS_DIST_IMAGE_PATH.exists():
        doc.add_picture(str(CLASS_DIST_IMAGE_PATH), width=Cm(15.5))
        add_caption(doc, "Рисунок 1 — Распределение файлов по классам датасета 3W")


def add_model_section(doc: Document, macro_f1: str, weighted_f1: str) -> None:
    add_heading_center(doc, "3 Обучение модели и оценка качества", level=1)
    add_paragraph(
        doc,
        "Для каждого CSV-эпизода формируется вектор статистических признаков: среднее значение, "
        "стандартное отклонение, минимум, максимум, медиана, квантили 10% и 90%, наклон линейного "
        "тренда, а также доля пропусков по каждому датчику. Дополнительно вычисляются длительность "
        "эпизода и доля корректных временных отметок."
    )

    add_paragraph(
        doc,
        "Ниже приведен ключевой фрагмент кода, реализующий конфигурацию модели и обучение "
        "в составе пайплайна scikit-learn:"
    )
    add_code_block(
        doc,
        'model = Pipeline(steps=[\n'
        '    ("imputer", SimpleImputer(strategy="median")),\n'
        '    ("clf", RandomForestClassifier(\n'
        '        n_estimators=200,\n'
        '        random_state=42,\n'
        '        n_jobs=-1,\n'
        '        class_weight="balanced"\n'
        "    ))\n"
        "])\n"
        "model.fit(x_train, y_train)\n"
        "y_pred = model.predict(x_test)\n"
    )

    add_paragraph(
        doc,
        "Разделение на обучающую и тестовую выборки выполнено в пропорции 80/20 со стратификацией "
        "по классам. Это позволило сохранить структуру дисбаланса классов и корректно оценить "
        "устойчивость алгоритма на редких событиях."
    )

    add_paragraph(
        doc,
        f"По итогам эксперимента получены следующие интегральные метрики: Macro F1 = {macro_f1}, "
        f"Weighted F1 = {weighted_f1}. Значения подтверждают высокую точность решения для "
        "учебного кейса и корректность построенного конвейера."
    )

    if CM_IMAGE_PATH.exists():
        doc.add_picture(str(CM_IMAGE_PATH), width=Cm(15.5))
        add_caption(doc, "Рисунок 2 — Матрица ошибок классификации (Confusion Matrix)")


def add_interface_section(doc: Document) -> None:
    add_heading_center(doc, "4 Программная реализация интерфейса", level=1)
    add_paragraph(
        doc,
        "Для практического использования модели создано мини-приложение на Streamlit. "
        "Интерфейс обеспечивает загрузку CSV-файла, запуск предсказания, вывод человекочитаемой "
        "интерпретации класса и формирование текстового отчета для последующего анализа."
    )
    add_paragraph(
        doc,
        "Сценарий работы пользователя: открыть веб-страницу, загрузить файл телеметрии, "
        "нажать кнопку запуска и получить результат. В интерфейсе отображаются основные "
        "гипотезы (top-3), уровень уверенности и пояснение по каждому классу."
    )
    add_paragraph(doc, "Ключевой фрагмент запуска веб-интерфейса:")
    add_code_block(
        doc,
        "cd C:\\AI\\ai_oil_3w\n"
        ".\\.venv\\Scripts\\Activate.ps1\n"
        "streamlit run app.py\n"
    )
    add_paragraph(
        doc,
        "Для командной эксплуатации предусмотрен режим CLI. Он полезен при пакетной обработке "
        "файлов или интеграции в простые скрипты мониторинга."
    )
    add_code_block(
        doc,
        "python project.py --predict .\\incoming\\my_case.csv\n"
    )


def add_practical_startup_section(doc: Document) -> None:
    add_heading_center(doc, "5 Инструкция запуска после включения компьютера", level=1)
    add_paragraph(
        doc,
        "После запуска операционной системы необходимо открыть PowerShell и перейти в каталог "
        "проекта. Затем активируется виртуальное окружение Python, после чего пользователь "
        "выбирает один из двух рабочих режимов: веб-интерфейс или командная строка."
    )
    add_code_block(
        doc,
        "cd C:\\AI\\ai_oil_3w\n"
        ".\\.venv\\Scripts\\Activate.ps1\n"
    )
    add_paragraph(
        doc,
        "Если требуется переобучение модели (например, после изменения кода или добавления новых "
        "данных), необходимо выполнить команду `python project.py`. Для повседневной эксплуатации "
        "без переобучения достаточно сразу запускать `streamlit run app.py`."
    )
    add_paragraph(
        doc,
        "Результаты предсказаний автоматически сохраняются в каталоге reports в виде текстовых "
        "файлов формата prediction_summary_*.txt, что обеспечивает документирование экспериментов."
    )


def add_conclusion(doc: Document) -> None:
    add_heading_center(doc, "ЗАКЛЮЧЕНИЕ", level=1)
    add_paragraph(
        doc,
        "В ходе выполнения работы разработан законченный прототип интеллектуальной системы "
        "классификации состояний нефтегазовой скважины на основе датасета 3W. Реализованы все "
        "основные этапы жизненного цикла ML-проекта: подготовка данных, извлечение признаков, "
        "обучение модели, количественная оценка качества и создание пользовательского интерфейса."
    )
    add_paragraph(
        doc,
        "Практическим результатом является программный комплекс, позволяющий работать как в "
        "режиме командной строки, так и через веб-интерфейс, с автоматическим формированием "
        "человекочитаемого отчета. Полученные метрики показывают высокую точность на тестовой "
        "выборке учебного набора данных."
    )
    add_paragraph(
        doc,
        "Перспективы развития проекта включают интеграцию с промышленными источниками телеметрии, "
        "добавление механизмов онлайн-обработки потоков данных и адаптацию модели под конкретные "
        "месторождения с учетом локальных технологических особенностей."
    )


def add_references(doc: Document) -> None:
    add_heading_center(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", level=1)
    refs = [
        "Vargas R. et al. A realistic and public dataset with rare undesirable real events in oil wells // Journal of Petroleum Science and Engineering.",
        "UCI Machine Learning Repository. 3W Dataset. URL: https://archive.ics.uci.edu/dataset/540/3w+dataset",
        "Petrobras 3W Repository. URL: https://github.com/petrobras/3W",
        "scikit-learn documentation. RandomForestClassifier. URL: https://scikit-learn.org/",
        "Streamlit documentation. URL: https://docs.streamlit.io/",
        "python-docx documentation. URL: https://python-docx.readthedocs.io/",
        "ГОСТ 7.32-2017. Отчет о научно-исследовательской работе. Структура и правила оформления.",
    ]
    for i, ref in enumerate(refs, start=1):
        p = doc.add_paragraph(f"{i}. {ref}")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Cm(0)


def add_appendix(doc: Document) -> None:
    add_heading_center(doc, "PRILOZHENIE A (fragments of source code)", level=1)
    add_paragraph(
        doc,
        "? ?????????? ????????? ??????????? ???????? ????, ??????????? ?????????? ??????, "
        "???????? ??????, ???????????? ? ???-?????????."
    )

    project_path = BASE_DIR / "project.py"
    app_path = BASE_DIR / "app.py"

    add_paragraph(doc, "A.1 ?????????? ? ??????? ????????.")
    add_code_block(doc, extract_function_source(project_path, "safe_numeric_series"))

    add_paragraph(doc, "A.2 ?????????? ????????? ?? ?????????? ????.")
    add_code_block(doc, extract_function_source(project_path, "extract_features"))

    add_paragraph(doc, "A.3 ?????????? ???????? ?? ????????? CSV ??????.")
    add_code_block(doc, extract_function_source(project_path, "build_dataset"))

    add_paragraph(doc, "A.4 ???????? ? ?????? ???????? ??????.")
    add_code_block(doc, extract_function_source(project_path, "train_and_evaluate"))

    add_paragraph(doc, "A.5 ?????????? ?????????? ???????? (??????, ???????, ???????????).")
    add_code_block(doc, extract_function_source(project_path, "save_outputs"))

    add_paragraph(doc, "A.6 ???????????? ?? ?????? ?????.")
    add_code_block(doc, extract_function_source(project_path, "predict_file"))

    add_paragraph(doc, "A.7 ???????????? ????????????????? ??????.")
    add_code_block(doc, extract_function_source(project_path, "run_prediction"))
    add_code_block(doc, extract_function_source(project_path, "write_prediction_report"))

    add_paragraph(doc, "A.8 ???????? ??? ???-?????????? Streamlit.")
    add_code_block(doc, extract_function_source(app_path, "main"))


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    counts = class_file_counts()
    macro_f1, weighted_f1 = parse_metrics()
    if counts:
        build_class_distribution_plot(counts)

    doc = Document()
    setup_page(doc)
    setup_styles(doc)
    setup_footer_with_page_number(doc)

    add_title_page(doc)
    add_abbreviations(doc)
    add_introduction(doc)
    add_theory(doc)
    add_dataset_section(doc, counts)
    add_model_section(doc, macro_f1, weighted_f1)
    add_interface_section(doc)
    add_practical_startup_section(doc)
    add_conclusion(doc)
    add_references(doc)
    add_appendix(doc)

    doc.save(OUTPUT_DOCX_PATH)
    print("Document created successfully.")
    print(f"Output file (UTF-8 name): {OUTPUT_DOCX_PATH.name.encode('utf-8', errors='ignore')}")
    print(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
