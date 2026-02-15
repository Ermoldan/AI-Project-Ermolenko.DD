# AI Oil&Gas 3W Project

Учебный проект по дисциплине «Искусственный интеллект».

## Что внутри
- `project.py` — обучение модели и предсказание по CSV.
- `app.py` — мини-приложение Streamlit для загрузки CSV через браузер.
- `build_poyasnitelnaya_zapiska.py` — генерация Word документа «Пояснительная записка».
- `reports/Пояснительная_записка_3W.docx` — готовая записка.

## Быстрый запуск
```powershell
cd C:\AI\ai_oil_3w
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

## CLI предсказание
```powershell
python project.py --predict .\incoming\my_case.csv
```

## Важно по данным
Raw-датасет `data/raw/3w` не включен в git (слишком большой).  
Для локального обучения нужен датасет 3W из UCI/Petrobras.

## Репозиторий
Проект подготовлен для загрузки на GitHub как студенческая работа.
