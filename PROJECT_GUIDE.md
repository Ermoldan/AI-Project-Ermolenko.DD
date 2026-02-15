# AI Oil&Gas 3W Project Guide

## 1. Chto my sdelali po shagам

1. Sozdali strukturu proekta (`data`, `models`, `reports`, `incoming`).
2. Zagruzili i raspakovali dataset 3W v `data/raw/3w`.
3. Napisali `project.py` dlya polnogo pipeline:
   - chtenie CSV,
   - izvlechenie priznakov iz vremennogo ryada,
   - obuchenie klassifikatora,
   - ocenka metrik,
   - sohranenie modeli i otchetov.
4. Dobavili predskazanie dlya odnogo novogo CSV:
   - `python project.py --predict <file.csv>`.
5. Dobavili chelovecheskie nazvaniya klassov i tekstovye opisaniya.
6. Dobavili avtomaticheskii txt-otchet v `reports/prediction_summary_*.txt`.
7. Sdelali mini-prilozhenie na Streamlit (`app.py`) s zagruzkoi CSV cherez browser.

---

## 2. Chto lezhit v papke proekta

Koren: `C:\AI\ai_oil_3w`

- `project.py`  
  Osnovnoi skript: train + predict + formirovanie txt-otcheta.
- `app.py`  
  Mini-web prilozhenie dlya zagruzki CSV i polucheniya rezultata bez komandnoi stroki.
- `PROJECT_GUIDE.md`  
  Etot podrobnyi guide.
- `build_word_guide.py`  
  Skript, kotoryi sozdaet Word dokument s gaidom.
- `requirements.txt`  
  Zavisimosti proekta.
- `data/raw/3w/0..8/`  
  Dataset (CSV po klassam).
- `incoming/`  
  Syuda ukladyvayutsya zagruzhennye ili testovye CSV dlya predskazaniya.
- `models/rf_3w.joblib`  
  Obuchennaya model.
- `models/feature_columns.json`  
  Spisok priznakov, v tom zhe poryadke, kak pri obuchenii.
- `reports/`  
  Otchety:
  - `classification_report.txt`
  - `confusion_matrix.png`
  - `prediction_summary_*.txt`
  - `Project_Guide_*.docx` (posle zapuska `build_word_guide.py`)

---

## 3. Pro dataset 3W (chto tam predstavleno)

3W = dataset po neftegazovoi skvazhine dlya raspoznavaniya normalnogo i avariinogo povedeniya.

- V nashoi kopii: `1984` CSV faila.
- Klassy: `0..8`.
- Kazhdyi CSV = odin epizod (vremennoi ryad) po skvazhine.
- Tipichnye kolonki:
  - `timestamp`
  - `P-PDG`
  - `P-TPT`
  - `T-TPT`
  - `P-MON-CKP`
  - `T-JUS-CKP`
  - `P-JUS-CKGL`
  - `T-JUS-CKGL`
  - `QGL`
  - `class` (metka, est v trening-dannykh)

Raspredelenie failov po klassam v tvoei papke:

- class 0: 597
- class 1: 129
- class 2: 38
- class 3: 106
- class 4: 344
- class 5: 451
- class 6: 221
- class 7: 14
- class 8: 84

---

## 4. Chto takoe klassy v proekte

- `0`: `normalnaya_rabota`  
  Normalnyi rabochii rezhim skvazhiny bez anomalii.
- `1`: `rezkii_rost_bsw`  
  Rezkii rost obvodnennosti.
- `2`: `lozhnoe_zakrytie_dhsv`  
  Oshi bochnoe zakrytie podzemnogo klapana.
- `3`: `tyazhelyi_slugging`  
  Tyazhelyi neravnomernyi potok.
- `4`: `nestabilnost_potoka`  
  Fluktuacii potoka / davlenii.
- `5`: `bystraya_poterya_proizvoditelnosti`  
  Bystraya prosadka proizvoditelnosti.
- `6`: `bystroe_suzhenie_v_pck`  
  Ogranichenie prohodimosti v choke-zone.
- `7`: `otlozheniya_v_pck`  
  Otlozheniya s postepennym uhudsheniem.
- `8`: `gidrat_v_linii_dobychi`  
  Risk blokirovki potoka gidratami.

---

## 5. Kakaya u nas model i kak ona rabotaet

Model: `RandomForestClassifier` (scikit-learn).

Pochemu:
- prostaya i nadezhnaya baza dlya uchebnogo proekta;
- horosho rabotaet s tablichnymi priznakami;
- ne trebuet slozhnoi normalizacii.

Pipeline:
1. Iz kazhdogo CSV schitaem agregirovannye priznaki po signalam:
   - mean, std, min, max, median, p10, p90, trend, nan_ratio.
2. Dobavlyaem vremennye priznaki:
   - `duration_sec`, `valid_timestamp_ratio`.
3. Chistim anomalnye znacheniya.
4. Delym na train/test.
5. Obuchaem RandomForest.
6. Schitaem metrikи (v tom chisle F1).
7. Sohranyaem model i otchety.

---

## 6. Kak zapuskat posle vklyucheniya kompjutera (poshagovo)

### Variant A: Mini-prilozhenie (rekomenduetsya)

1. Otkroi PowerShell.
2. Vvedi:

```powershell
cd C:\AI\ai_oil_3w
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

3. Otkroisya ssylka tipa `http://localhost:8501`.
4. V browser:
   - zagruzhaesh CSV,
   - nazhimaesh "Zapustit predskazanie",
   - smotrish rezultat i skachivaesh txt-otchet.

### Variant B: Cherez komandnuyu stroku

```powershell
cd C:\AI\ai_oil_3w
.\.venv\Scripts\Activate.ps1
python project.py --predict .\incoming\my_case.csv
```

Rezultat:
- vyvod v konsol,
- text otchet v `reports/prediction_summary_*.txt`.

---

## 7. Kogda nuzhno pereobuchat model

Obuchenie:

```powershell
cd C:\AI\ai_oil_3w
.\.venv\Scripts\Activate.ps1
python project.py
```

Delat pereobuchenie nuzhno, esli:
- ty pomenyal kod priznakov;
- dobavil novye trening CSV;
- hochesh obnovit metrikи.

---

## 8. Kak ispolzovat ne gotovyi dataset, a svoi keis

Nuzhno podgotovit CSV s teh zhe signalami:
- `timestamp`, `P-PDG`, `P-TPT`, `T-TPT`, `P-MON-CKP`, `T-JUS-CKP`, `P-JUS-CKGL`, `T-JUS-CKGL`, `QGL`.

`class` v novom faile ne obyazatelen.

Primer:
1. Vzyat interval dannyh skvazhiny (naprimer 5-10 minut).
2. Sohranit kak `incoming/my_case.csv`.
3. Provesti predskazanie cherez `app.py` ili CLI.
4. Izuchit `prediction_summary_*.txt`.

---

## 9. Ogranicheniya (vazhno dlya zashity)

1. Eto model podderzhki reshenii, a ne avto-upravlenie skvazhinoi.
2. Kachestvo zavisit ot skhodstva realnyh dannyh s 3W.
3. Esli u mestorozhdeniya drugie usloviya/scale signalov, nuzhna lokalnaya adaptaciya i pereobuchenie.
4. Pri nizkoi uverennosti (`low_confidence`) rezultat obyzatelno proveriaetsya inzhenerom.

---

## 10. Bystraya shpargalka komand

Aktivaciya okruzheniya:

```powershell
cd C:\AI\ai_oil_3w
.\.venv\Scripts\Activate.ps1
```

Obuchenie:

```powershell
python project.py
```

Predskazanie po CSV:

```powershell
python project.py --predict .\incoming\my_case.csv
```

Zapusk mini-app:

```powershell
streamlit run app.py
```
