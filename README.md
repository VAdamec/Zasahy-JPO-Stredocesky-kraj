# 🚒 Zásahy JPO – Středočeský kraj a Fire Brno

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-03A9F4.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/VAdamec/Zasahy-JPO-Stredocesky-kraj)](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/releases)

Integrace pro Home Assistant, která sleduje **výjezdy hasičů** ze dvou zdrojů:

- [PKR Středočeského kraje](https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/) – HTML přehled zásahů s filtrem podle okresu a stupně poplachu.
- [Fire Brno](https://udalosti.firebrno.cz/) – JSON backend přehledu HZS s výběrem kraje a okresu podle nabídky zdroje; výchozí je Jihomoravský kraj.

V HA z nich dělá společné senzory a eventy pro notifikace a dashboard.
Tento fork vychází z [původní integrace od LochyCZ](https://github.com/LochyCZ/Zasahy-JPO-Stredocesky-kraj).

> *English: Home Assistant custom integration that tracks fire brigade incidents in the
> Central Bohemian Region through PKR and regions offered by Fire Brno.
> Both providers share sensors and incident events. The UI is in Czech and English.*

## Co umí

- **Dva zdroje:** PKR s URL filtrem podle okresu a stupně poplachu; Fire Brno s výběrem kraje a okresu v HA.
- **Senzory:** dnešní zásahy, probíhající zásahy, přehled za poslední týden a poslední zásah.
- **Event při novém výjezdu**, takže notifikaci dostaneš jen pro obce, které tě zajímají.
- **Event při změně stavu**, třeba když zásah přejde z probíhajícího na ukončený.
- **Nastavení celé přes UI**, bez YAML. Víc okresů = víc instancí.
- **Žádné notifikace navíc po restartu:** první načtení se jen zapamatuje.
- **Šetří databázi:** seznamy zásahů se neukládají do recorderu.

## Instalace

### HACS (doporučeno)

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=VAdamec&repository=Zasahy-JPO-Stredocesky-kraj&category=integration)

Nebo ručně: **HACS → ⋮ → Custom repositories**, vlož `https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj`
a jako typ zvol **Integration**. Pak integraci najdi v HACS, nainstaluj ji a restartuj Home Assistant.

### Ručně

1. Stáhni si poslední [release](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/releases).
2. Složku `custom_components/pkr_zasahy` zkopíruj do `/config/custom_components/`.
3. Restartuj Home Assistant.

## Nastavení

[![Přidat integraci](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pkr_zasahy)

Při přidání integrace nejdřív vyber zdroj dat. Každý zdroj a filtr může mít vlastní instanci.
Existující PKR instance fungují bez nového nastavení a zachovají ID entit.

### PKR – Středočeský kraj

1. Otevři [stránku zásahů](https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/) a v pravém panelu
   **Filtr** si vyber okres. Můžeš přidat i stupeň poplachu.
2. Zkopíruj adresu z prohlížeče.
3. V HA otevři **Nastavení → Zařízení a služby → Přidat integraci → Zásahy JPO** a adresu vlož.

Název instance se doplní sám podle filtru, například *Zásahy JPO – okres Rakovník*.
Výchozí adresa vede na okres Rakovník:

```
https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/?q=&r_cast_uzemi__in=1192
```

### Fire Brno

1. V **Nastavení → Zařízení a služby → Přidat integraci → Zásahy JPO** vyber **Fire Brno (HZS)**.
2. Vyber kraj; výchozí je **Jihomoravský**.
3. Vyber okres nebo ponech celý kraj. Kopírování URL z prohlížeče není potřeba.

Nabídku krajů a okresů dodává zdroj. Její přítomnost sama nezaručuje úplné pokrytí daty.
Příklad názvu instance: *Zásahy JPO – Brno-město*.

**Interval kontroly** změníš v **Konfigurovat**: 5–60 minut, výchozí je 10.

## Entity

Názvy entit se tvoří z názvu instance. Níže jsou ID pro HA v češtině a okres Rakovník.

| Entita | Stav | Atributy |
|---|---|---|
| `sensor.zasahy_jpo_okres_rakovnik_zasahy_dnes` | počet dnešních zásahů | `zasahy` |
| `sensor.zasahy_jpo_okres_rakovnik_probihajici_zasahy` | počet neukončených zásahů | `zasahy` |
| `sensor.zasahy_jpo_okres_rakovnik_zasahy_za_posledni_tyden` | počet zásahů v seznamu na webu | `zasahy` |
| `sensor.zasahy_jpo_okres_rakovnik_posledni_zasah` | název posledního zásahu | pole posledního zásahu (viz níže) |
| `sensor.zasahy_jpo_okres_rakovnik_cas_posledniho_zasahu` | čas posledního zásahu (timestamp) | – |

Přesná ID si ověříš v **Vývojářské nástroje → Stavy**.

### Pole zásahu

Tato pole má každá položka v atributu `zasahy` a také data eventů.

| Pole | Příklad | Popis |
|---|---|---|
| `nazev` | `požár - lesní porost - Mšecké Žehrovice` | celý název z webu |
| `kategorie` | `požár` | požár, dopravní nehoda, technická pomoc, únik nebezpečných látek, záchrana osob a zvířat… |
| `podtyp` | `lesní porost` | upřesnění události |
| `typ` | `požár` | typ podle ikony na webu |
| `stav` | `ukončená` | stav události |
| `aktivni` | `false` | aktivní stav podle pravidel zdroje; u neznámého stavu Fire Brno `null` |
| `obec` | `Mšecké Žehrovice` | místo události |
| `okres` | `Rakovník` | u okresního města bývá `null` |
| `stupen` | `I.` | PKR: `I.`, `II.`, `III.` nebo `Z`; Fire Brno: `null` |
| `cas` | `2026-10-03T14:10:00+02:00` | PKR: poslední aktualizace; Fire Brno: čas ohlášení (ISO 8601) |
| `id` | `a1b2c3d4e5f6` | PKR: identifikátor řádku; Fire Brno: stabilní `firebrno:<id>` |

Fire Brno navíc poskytuje `provider`, `native_id`, `stav_id`, `cas_ohlaseni`,
`cas_vzniku`, `kraj`, `cast_obce`, `orp`, `ulice`, `silnice` a `poznamka`.
Volitelná pole mohou být `null`. `cas_aktualizace` je `null`, protože backend
čas poslední změny neposkytuje. Kategorie a podtypy jsou převedené na malá písmena.
Souřadnice zdroje se nepřevádějí ani nepoužívají jako GPS.

## Eventy

| Event | Kdy se vyšle | Pole navíc |
|---|---|---|
| `pkr_zasahy_novy_zasah` | V seznamu se objeví nový zásah. | `entry_id`, `provider`, `source_url` |
| `pkr_zasahy_aktualizace_zasahu` | PKR: známý název a obec dostanou novější čas; Fire Brno: stejnému nativnímu ID se změní obsah, i bez změny času ohlášení. | `entry_id`, `predchozi_stav`, `provider`, `source_url` |

Pokud máš více instancí, filtruj eventy podle `entry_id` nebo `provider`
(`pkr` / `firebrno`). Překrývající se instance posílají vlastní eventy.

## Příklady

### Notifikace pro vybrané obce

```yaml
alias: "Hasiči – výjezd v okolí"
mode: queued
triggers:
  - trigger: event
    event_type: pkr_zasahy_novy_zasah
conditions:
  - condition: template
    value_template: >
      {{ trigger.event.data.obec in ['Rakovník', 'Lužná', 'Senomaty'] }}
actions:
  - action: notify.mobile_app_telefon
    data:
      title: >
        🚒 {{ trigger.event.data.kategorie | capitalize }} – {{ trigger.event.data.obec }}
      message: >
        {{ trigger.event.data.podtyp }} · {{ trigger.event.data.stav }}
        · stupeň {{ trigger.event.data.stupen }}
      data:
        url: "https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/?q=&r_cast_uzemi__in=1192"
```

Další užitečné podmínky:

```jinja
{{ trigger.event.data.kategorie == 'požár' }}   {# jen požáry #}
{{ trigger.event.data.stupen != 'I.' }}         {# jen vyšší stupeň poplachu #}
```

### Fire Brno – notifikace pro Brno

```yaml
alias: "Hasiči – Fire Brno"
mode: queued
triggers:
  - trigger: event
    event_type: pkr_zasahy_novy_zasah
conditions:
  - condition: template
    value_template: >
      {{ trigger.event.data.provider == 'firebrno' and trigger.event.data.obec == 'Brno' }}
actions:
  - action: notify.mobile_app_telefon
    data:
      title: "🚒 {{ trigger.event.data.kategorie | capitalize }} – {{ trigger.event.data.obec }}"
      message: >
        {{ trigger.event.data.podtyp }} · {{ trigger.event.data.stav }}
        {% if trigger.event.data.poznamka %} · {{ trigger.event.data.poznamka }}{% endif %}
      data:
        url: "{{ trigger.event.data.source_url }}"
```

### Oznámení o ukončení zásahu

```yaml
alias: "Hasiči – zásah ukončen"
triggers:
  - trigger: event
    event_type: pkr_zasahy_aktualizace_zasahu
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.aktivni == false }}"
actions:
  - action: notify.mobile_app_telefon
    data:
      message: "✅ {{ trigger.event.data.nazev }} – ukončeno"
```

### Karta do dashboardu

```yaml
type: markdown
title: 🚒 Zásahy – okres Rakovník
content: |
  {% set z = state_attr('sensor.zasahy_jpo_okres_rakovnik_zasahy_za_posledni_tyden', 'zasahy') or [] %}
  | Čas | Událost | Obec | Stav |
  |---|---|---|---|
  {% for i in z[:10] -%}
  | {{ as_timestamp(i.cas) | timestamp_custom('%d.%m. %H:%M') }} | {{ i.kategorie }} – {{ i.podtyp }} | {{ i.obec }} | {{ '🔴' if i.aktivni else '⚪' }} {{ i.stav }} |
  {% endfor %}
```

## Jak to funguje

PKR provider stáhne HTML a přečte tabulku zásahů. Zachovává původní porovnání:
stejný název a obec s novějším časem do 6 hodin znamenají aktualizaci.

Fire Brno provider používá nedokumentovaný JSON backend webové aplikace.
Číselníky typů, podtypů a stavů ukládá do paměti na den. Nový neznámý kód vyvolá
nejvýše jeden dodatečný pokus o obnovení denně. Při výpadku číselníků lze použít
platnou paměťovou kopii. Každá aktualizace načte sedmidenní historii a starší
záznamy do 30 dní, aby zachytila také ukončení již sledovaných zásahů.
Události porovnává podle nativního ID a obsahu. Zmizelý záznam se automaticky
neoznačuje jako ukončený.

Oba providery používají společný coordinator, senzory a eventy. První úspěšné
načtení po startu pouze naplní paměť. Chyba HTTP, JSON nebo struktury dat nastaví
senzory jako nedostupné; není považována za prázdný seznam.

## Omezení

- **Data jsou zpožděná a orientační.** Web to sám uvádí a události zveřejňuje tak,
  jak byly vyhodnoceny při vzniku.
- **PKR ukazuje čas poslední aktualizace**, podle něj se počítají dnešní zásahy.
  **Fire Brno používá čas ohlášení**. Nejnovější zásah znamená u Fire Brno poslední
  ohlášený zásah, nikoli naposledy změněný.
- **PKR ukazuje zhruba poslední týden.** Fire Brno poskytuje v týdenním senzoru
  posledních 7 dní; probíhající zásahy kontrolujeme do 30 dní od ohlášení.
  Starší otevřené zásahy nejsou zahrnuté. Úplnost historie ani případné serverové
  omezení počtu záznamů nelze z nedokumentovaného API zaručit.
- **Fire Brno stav určuje podle číselného kódu.** Kód `500` web řadí mezi otevřené,
  i když jeho text zní „Ukončená“. Nový neznámý kód má `aktivni: null`; počet
  probíhajících zásahů pak bude `unknown` s atributem `neznamy_stav`.
  V automatizacích pro ukončení používej `aktivni == false`.
- **Stupeň poplachu Fire Brno neposkytuje** v používaném seznamu. Filtry podle
  stupně poplachu jsou určené pro PKR.
- **Integrace závisí na struktuře webu.** Když se HTML změní, senzory přejdou do stavu
  *nedostupné* a v logu bude „Zdroj má neočekávanou strukturu“. V tom případě
  [založ issue](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/issues).
- **Neptej se moc často.** Web automatické stahování nevítá. Kratší interval než
  5 minut integrace nepovolí a výchozích 10 minut na notifikace bohatě stačí.

## Vývoj

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests
.venv/bin/ruff check custom_components tests
```

`tests/test_parser.py` testuje parser na uložené kopii stránky a nepotřebuje
Home Assistant, stačí `pytest`. Fire Brno testy používají malé syntetické JSON
fixtures odpovídající ověřenému schématu. Integrační testy pouštějí config flow,
senzory, načtení starých konfigurací, výpadky a eventy v testovací instanci HA.
Žádný automatický test nepřistupuje k živému zdroji.

Logování pro ladění:

```yaml
logger:
  logs:
    custom_components.pkr_zasahy: debug
```

## Upozornění

Neoficiální projekt, který nemá nic společného se Středočeským krajem ani s HZS ČR.
Na notifikace z této integrace nespoléhej v situacích, kde jde o bezpečnost.
Data patří jejich provozovateli.

## Licence

[MIT](LICENSE)
