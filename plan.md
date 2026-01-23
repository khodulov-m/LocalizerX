# LocalizerX — План реализации

## 1. Обзор проекта
**LocalizerX** — CLI‑инструмент для macOS (Python), предназначенный для автоматического добавления переводов в Xcode String Catalogs (`.xcstrings`) с использованием **Gemini API**.

Назначение:
- Чтение одного файла `.xcstrings` или каталога с такими файлами
- Автоматический перевод строк на указанные языки
- Корректная работа с placeholders, вариациями и плюрализацией
- Безопасная и воспроизводимая запись результатов

---

## 2. Цели и нефункциональные требования

### Функциональные цели
- CLI‑утилита `localizerx`
- Поддержка:
  - одного файла `.xcstrings`
  - каталога с несколькими `.xcstrings`
- Добавление переводов для указанных языков
- Поддержка режимов:
  - `--dry-run`
  - `--preview`
  - `--apply`
  - `--resume`
- Работа с существующими переводами:
  - `--skip-existing`
  - `--overwrite`

### Нефункциональные требования
- Lossless‑парсинг и запись `.xcstrings`
- Асинхронные запросы к Gemini API
- Retry / backoff / rate‑limit
- Кэширование переводов
- Резервное копирование файлов
- Минимальные внешние зависимости

---

## 3. Высокоуровневая архитектура

```text
CLI
 └─ File Scanner
     └─ xcstrings Parser
         └─ Translation Queue
             └─ Gemini API Adapter
                 └─ Post‑processing (placeholders, plurals)
                     └─ Writer + Backup
```

Модули изолированы, переводчик абстрагирован от CLI и формата файлов.

---

## 4. Структура репозитория

```text
localizerx/
├─ localizerx/
│  ├─ __main__.py
│  ├─ cli.py
│  ├─ config.py
│  ├─ io/
│  │  └─ xcstrings.py
│  ├─ parser/
│  │  └─ model.py
│  ├─ translator/
│  │  ├─ base.py
│  │  └─ gemini_adapter.py
│  ├─ utils/
│  │  ├─ placeholders.py
│  │  ├─ locale.py
│  │  └─ logging.py
├─ tests/
├─ examples/
│  └─ Localizable.xcstrings
├─ pyproject.toml
└─ PLAN.md
```

---

## 5. CLI интерфейс

### Основная команда
```bash
localizerx translate <path> --to fr,es,de --src en
```

### Поддерживаемые опции
- `--src <lang>` — исходный язык (по умолчанию `en`)
- `--to <langs>` — целевые языки (через запятую)
- `--dry-run` — без записи
- `--preview` — показать изменения
- `--apply` — применить изменения
- `--overwrite`
- `--skip-existing`
- `--backup`
- `--resume`
- `--config <path>`
- `--concurrency <n>`
- `--batch-size <n>`

CLI реализуется на **Typer**.

---

## 6. Работа с `.xcstrings`

- Формат: JSON‑подобная структура Xcode String Catalog
- Поддержка:
  - ключей
  - базового языка
  - переводов
  - комментариев разработчика
  - plural / variations

Требование: `read → write` без изменений структуры, кроме добавленных переводов.

---

## 7. Модель данных (внутренняя)

```python
Entry:
  key: str
  source_text: str
  comment: str | None
  translations: dict[lang, Translation]

Translation:
  value: str
  variations: dict | None
```

---

## 8. Интеграция с Gemini API

### Подход
- Асинхронный HTTP‑адаптер
- Абстракция `Translator` → возможность замены провайдера

### Функции адаптера
- Аутентификация через env `GEMINI_API_KEY`
- Батчинг строк
- Retry + exponential backoff
- Rate limiting
- Учёт лимитов токенов

### Контекст перевода
В каждый запрос передаётся:
- исходный язык
- целевой язык
- ключ строки
- комментарий разработчика
- инструкция сохранять placeholders

---

## 9. Placeholders и плюрализация

### Placeholders
- Маскирование перед переводом (`%@`, `%d`, `{name}` → `__PH_1__`)
- Восстановление после перевода

### Plural / Variations
- Перевод каждой формы отдельно
- Явное указание контекста формы (`one`, `other`, etc.)

---

## 10. Кэширование и надёжность

- SQLite‑кэш:
  - ключ: `(src_lang, tgt_lang, text_hash)`
- Повторный запуск не переводит уже обработанные строки
- Поддержка `--resume`

---

## 11. Конфигурация

Расположение:
```text
~/.config/localizerx/config.toml
```

Содержимое:
- API ключи
- настройки concurrency
- batch size
- политика overwrite

---

## 12. Логирование и контроль стоимости

- Уровни логов: INFO / DEBUG / ERROR
- Подсчёт количества символов/строк
- Предварительная оценка стоимости перед `--apply`

---

## 13. Тестирование

### Unit tests
- Парсер `.xcstrings`
- Placeholder masking
- Locale mapping

### Integration tests
- Mock Gemini API
- End‑to‑end перевод файла

### Snapshot tests
- Входной `.xcstrings` → ожидаемый результат

---

## 14. CI / Release

- GitHub Actions:
  - lint (ruff)
  - format (black)
  - tests (pytest)
- Packaging:
  - `pip install localizerx`
- GitHub Releases

---

## 15. Этапы реализации (Roadmap)

1. CLI skeleton + структура проекта
2. Парсер и writer `.xcstrings`
3. Модель данных
4. Mock translator
5. Placeholders masking
6. Gemini API адаптер
7. Кэш и resume
8. Preview / apply режимы
9. Тесты
10. Документация и релиз

---

## 16. Открытые вопросы
- Политика перезаписи существующих переводов
- Максимальная длина строк
- Поддержка сложных ICU‑форм
- CI‑интеграция в iOS‑проекты

---

**Документ является живым и обновляется по мере развития проекта LocalizerX.**

