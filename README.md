# passport-ocr-postprocessing
Постобработка OCR паспорта РФ: accept/reject + извлечение 10 полей. MRZ-кросс-чек, проверка действительности на 01.10.2026, char_conf-фильтр.
# Постобработка OCR паспорта РФ

Решение тестового задания: по каждому документу принять (`accept` с 10 полями) или отклонить (`reject`).

## Запуск

```bash
python postprocess.py data/test_predictions.jsonl answers.jsonl
Зависимостей нет (только stdlib: json, sys, datetime), CPU, без интернета.

Метрика на train
bash
python score.py answers_train.jsonl data/train_labels.jsonl
Результат
Набор	accept	precision	recall
train	1403 / 3000	93.2%	43.6%
test	936 / 2000	~93% (прогноз)	—
Подробности — в REPORT.md.
