# Постобработка OCR паспорта РФ

Решение тестового задания: по каждому документу принять (`accept` с 10 полями) или отклонить (`reject`).

## Запуск

В терминале выполните команду:

python postprocess.py data/test_predictions.jsonl answers.jsonl

Зависимостей нет (только стандартная библиотека Python 3.8+: `json`, `sys`, `datetime`). Работает на CPU, без интернета.

## Метрика на train

Для проверки качества на train (с учётом действительности паспорта на 01.10.2026):

python score.py answers_train.jsonl data/train_labels.jsonl

## Результат

| Набор | accept | precision | recall |
|---|---|---|---|
| train | 1403 / 3000 | 93.2% | 43.6% |
| test  | 936 / 2000  | ~93% (прогноз) | — |
