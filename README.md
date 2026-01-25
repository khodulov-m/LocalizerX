# LocalizerX

CLI-инструмент для автоматического перевода Xcode String Catalogs (`.xcstrings`) с использованием Gemini API.

## Возможности

- Перевод `.xcstrings` файлов на несколько языков одной командой
- Сохранение плейсхолдеров (`%@`, `%d`, `{name}`) при переводе
- Поддержка плюрализации и форм склонения
- Учёт комментариев разработчика для контекста перевода
- Кэширование переводов в SQLite для экономии API-запросов
- Создание бэкапов перед изменениями

## Установка

### Требования

- macOS
- Python 3.10+
- API ключ Gemini

### Через pipx (рекомендуется)

```bash
# Установить pipx если ещё не установлен
brew install pipx
pipx ensurepath

# Установить LocalizerX
pipx install localizerx
```

### Из исходников

```bash
# Клонировать репозиторий
git clone https://github.com/localizerx/localizerx.git
cd localizerx

# Установить глобально
pipx install .

# Или для разработки (изменения применяются сразу)
pipx install -e .
```

### Через pip

```bash
pip install localizerx
```

## Настройка

### API ключ

Установите переменную окружения с вашим Gemini API ключом:

```bash
export GEMINI_API_KEY="your-api-key"
```

Для постоянного использования добавьте в `~/.zshrc` или `~/.bashrc`:

```bash
echo 'export GEMINI_API_KEY="your-api-key"' >> ~/.zshrc
```

### Файл конфигурации

Создайте конфигурационный файл:

```bash
localizerx init
```

Конфиг создаётся в `~/.config/localizerx/config.toml`:

```toml
[translator]
model = "gemini-2.0-flash"
batch_size = 10
max_retries = 3

[cache]
enabled = true
```

## Использование

### Перевод файла

```bash
# Перевести на французский, испанский и немецкий
localizerx translate Localizable.xcstrings --to fr,es,de

# Указать исходный язык (по умолчанию английский)
localizerx translate Localizable.xcstrings --to ru --src en

# Перевести все .xcstrings в директории
localizerx translate ./MyApp --to fr,es,de
```

### Опции команды translate

| Опция | Сокращение | Описание |
|-------|------------|----------|
| `--to` | `-t` | Целевые языки через запятую |
| `--src` | `-s` | Исходный язык (по умолчанию: `en`) |
| `--dry-run` | `-n` | Показать что будет переведено без изменений |
| `--preview` | `-p` | Предпросмотр переводов перед применением |
| `--overwrite` | | Перезаписать существующие переводы |
| `--backup` | `-b` | Создать бэкап (по умолчанию: включено) |
| `--batch-size` | | Количество строк за один API запрос (1-50) |
| `--config` | `-c` | Путь к файлу конфигурации |

### Просмотр информации о файле

```bash
localizerx info Localizable.xcstrings
```

Выводит статистику: количество строк, языки, покрытие переводами.

### Список поддерживаемых языков

```bash
localizerx languages
```

### Проверка версии

```bash
localizerx --version
```

## Примеры

### Dry run — посмотреть что будет переведено

```bash
localizerx translate App.xcstrings --to fr,de --dry-run
```

### Перевод с предпросмотром

```bash
localizerx translate App.xcstrings --to ja --preview
```

Покажет таблицу переводов и запросит подтверждение перед сохранением.

### Перезапись существующих переводов

```bash
localizerx translate App.xcstrings --to es --overwrite
```

### Пакетная обработка проекта

```bash
localizerx translate ~/Projects/MyApp --to fr,es,de,ja,ko,zh-Hans
```

Найдёт и переведёт все `.xcstrings` файлы в директории.

## Разработка

```bash
# Клонировать и установить зависимости
git clone https://github.com/localizerx/localizerx.git
cd localizerx
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Линтинг
ruff check .

# Форматирование
black .

# Тесты
pytest
```

## Лицензия

MIT
