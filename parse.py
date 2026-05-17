"""
Парсер сборника заданий первой части ЕГЭ-2026 (А. Чубуков).
На вход — PDF, на выход — questions.json со структурой:
[
  {
    "id": "1.1-1",
    "topic_code": "1.1",
    "topic_title": "Человек как биосоциальное существо...",
    "task_type": 1,            # номер из скобок — формат задания (1, 2, 3...)
    "number_in_topic": 1,      # порядковый № внутри темы
    "question": "текст задания",
    "options": ["1) ...", "2) ..."],   # варианты ответа, если есть
    "answer": "25"
  },
  ...
]
"""
import json
import re
import subprocess
from pathlib import Path

PDF = "/mnt/user-data/uploads/26_задания_первой_части_ЕГЭ_2026_Антона_Чубукова.pdf"
OUT = Path("/home/claude/questions.json")

# 1. Извлекаем текст с сохранением layout
raw = subprocess.check_output(
    ["pdftotext", "-layout", PDF, "-"], text=True
)

# 2. Чистим повторяющиеся колонтитулы и пустые строки
HEADER_RE = re.compile(
    r"(?:Сборник заданий в формате 2026 года.*?\n.*?vk\.com/club71258816\n)",
    re.MULTILINE,
)
text = HEADER_RE.sub("", raw)
# form-feed между страницами больше не нужен
text = text.replace("\f", "\n")

lines = [ln.rstrip() for ln in text.split("\n")]

# 3. Находим заголовки тем. Они выглядят как:
#    "1.1 Человек как биосоциальное существо..."
#    "2.4, 2.11 Экономическая деятельность..."
#    "1.13, 5.12 Образование..."
# Но такие же строки бывают в оглавлении с точками-разделителями и номером страницы.
# Реальный заголовок темы НЕ оканчивается на "... 15" (стр. оглавления).
TOPIC_RE = re.compile(
    r"^\s*((?:\d+\.\d+)(?:,\s*\d+\.\d+)*)\.?\s+([А-ЯЁ][^\n]+?)\s*$"
)

# Чтобы отличить заголовок в основной части от строки оглавления,
# ищем заголовки только после того, как кончится оглавление.
# Оглавление кончается после строки про "Как получить результаты...".
toc_end = next(
    i for i, ln in enumerate(lines)
    if "Как получить результаты теста-формы" in ln
)
# Сдвинемся чуть дальше — первая тема "1.1" встретится повторно уже как заголовок
body_start = toc_end + 1


def is_topic_header(line: str) -> bool:
    if "..." in line:           # строка оглавления
        return False
    m = TOPIC_RE.match(line)
    if not m:
        return False
    # отсекаем нумерованные пункты вроде "1) что-то" — у них точки нет
    # отсекаем "Ответ:"-строки и прочее
    return True


# 4. Разбиваем body на блоки тем
topics = []          # [(code, title, start_idx)]
current = None
for i in range(body_start, len(lines)):
    ln = lines[i]
    m = TOPIC_RE.match(ln)
    if m and "..." not in ln and not ln.strip().startswith("Ответ"):
        code_str = m.group(1)             # "1.1" или "2.4, 2.11"
        title = m.group(2).strip().rstrip(".")
        topics.append({"code": code_str, "title": title, "start": i})

# Добавим виртуальную "конечную" границу
topics.append({"code": None, "title": None, "start": len(lines)})

# 5. Для каждой темы — разобрать вопросы
QUESTION_START_RE = re.compile(r"^(\d+)\s*\((\d+)\)\s*\*?\s*(.*)$")
ANSWER_RE = re.compile(r"^\s*Ответ:\s*(.+?)\s*$")

all_questions = []
parse_errors = []

for ti in range(len(topics) - 1):
    topic = topics[ti]
    next_start = topics[ti + 1]["start"]
    block = lines[topic["start"] + 1 : next_start]

    # Внутри блока пропускаем «таблицу ответов» в начале (строки вида "1   25").
    # Реальные вопросы начинаются с "1 (1) ..." или "1 (2) ..."
    qstart_indices = []
    for j, ln in enumerate(block):
        if QUESTION_START_RE.match(ln):
            qstart_indices.append(j)

    # Часто первое попадание — это строка из таблицы вида "1   25"
    # потому что таких в таблице нет, но на всякий случай:
    qstart_indices = [
        j for j in qstart_indices
        if QUESTION_START_RE.match(block[j]).group(3).strip() != ""
    ]

    # Добавим виртуальную правую границу
    qstart_indices.append(len(block))

    for k in range(len(qstart_indices) - 1):
        s = qstart_indices[k]
        e = qstart_indices[k + 1]
        qblock = block[s:e]
        header = qblock[0]
        m = QUESTION_START_RE.match(header)
        number_in_topic = int(m.group(1))
        task_type = int(m.group(2))
        first_line = m.group(3).strip()

        # Собираем весь текст до строки "Ответ:"
        text_lines = [first_line] if first_line else []
        answer = None
        for ln in qblock[1:]:
            am = ANSWER_RE.match(ln)
            if am:
                answer = am.group(1).strip()
                break
            text_lines.append(ln)

        if answer is None:
            parse_errors.append(
                f"Тема {topic['code']} вопрос {number_in_topic}: не найден ответ"
            )
            continue

        # Разделяем формулировку и варианты ответа (строки "1) ...", "2) ...")
        opt_re = re.compile(r"^\s*(\d+)\)\s*(.*)$")
        question_parts = []
        options = []
        current_opt = None
        for ln in text_lines:
            om = opt_re.match(ln)
            if om:
                if current_opt is not None:
                    options.append(current_opt.strip())
                current_opt = f"{om.group(1)}) {om.group(2)}"
            else:
                if current_opt is not None:
                    current_opt += " " + ln.strip()
                else:
                    question_parts.append(ln.strip())
        if current_opt is not None:
            options.append(current_opt.strip())

        question_text = " ".join(p for p in question_parts if p).strip()
        question_text = re.sub(r"\s+", " ", question_text)
        options = [re.sub(r"\s+", " ", o) for o in options]

        all_questions.append({
            "id": f"{topic['code'].replace(', ', '_')}-{number_in_topic}",
            "topic_code": topic["code"],
            "topic_title": topic["title"],
            "task_type": task_type,
            "number_in_topic": number_in_topic,
            "question": question_text,
            "options": options,
            "answer": answer,
        })

OUT.write_text(
    json.dumps(all_questions, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Тем разобрано: {len(topics) - 1}")
print(f"Вопросов сохранено: {len(all_questions)}")
print(f"Ошибок парсинга: {len(parse_errors)}")
for err in parse_errors[:10]:
    print("  ", err)
