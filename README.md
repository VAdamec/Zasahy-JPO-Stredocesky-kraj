# 🚒 Zásahy JPO

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-03A9F4.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/VAdamec/Zasahy-JPO-Stredocesky-kraj)](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/releases)

Integrace pro Home Assistant, která sleduje **zásahy hasičů z více zdrojů**.
Vybereš zdroj a oblast, kterou chceš sledovat. Integrace vytvoří senzory pro dashboard
a posílá eventy pro automatizace a notifikace. Oba zdroje používají společné základní senzory
a pole zásahů. Fire Brno navíc poskytuje měsíční a roční přehled. Zdroje se liší
dostupnými filtry, časem události a rozsahem historie.

> *English: Home Assistant custom integration for fire brigade incidents from multiple
> data providers. Select a provider and area, then use shared sensors and events for
> dashboards and notifications. The UI is available in Czech and English.*

## Zdroje dat

| Zdroj | Oblast a filtry | Nastavení |
|---|---|---|
| [PKR Středočeského kraje](https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/) | Středočeský kraj; okres a volitelně stupeň poplachu | vložení URL s filtrem z webu |
| [Fire Brno – přehled HZS](https://udalosti.firebrno.cz/) | kraje a okresy nabízené zdrojem, volitelně zasahující jednotka; výchozí kraj je Jihomoravský | výběr oblasti a vyhledání jednotky přímo v HA |

Každý zdroj a filtr může mít vlastní instanci. Nabídka oblastí pochází od zdroje
a sama o sobě nezaručuje úplné pokrytí daty.

Projekt vychází z [původní integrace pro Středočeský kraj od LochyCZ](https://github.com/LochyCZ/Zasahy-JPO-Stredocesky-kraj).
Technická doména `pkr_zasahy` a názvy eventů zůstávají zachované pro oba zdroje,
aby fungovaly i existující konfigurace a automatizace.

## Co umí

- **Výběr zdroje a oblasti přes UI**, bez YAML konfigurace integrace.
- **Společné senzory:** dnešní zásahy, probíhající zásahy, týdenní přehled, poslední zásah a jeho čas.
- **Fire Brno navíc:** zásahy v aktuálním měsíci a roce, včetně počtu a úplného seznamu vráceného zdrojem.
- **Event při novém zásahu** pro vlastní notifikace, například jen pro vybrané obce.
- **Event při aktualizaci zásahu**, například při změně stavu.
- **Více instancí** pro různé zdroje nebo oblasti.
- **Bez historických notifikací po restartu:** první načtení pouze naplní paměť.
- **Seznamy zásahů se neukládají do recorderu**, aby zbytečně nezvětšovaly databázi.

## Instalace

### HACS (doporučeno)

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=VAdamec&repository=Zasahy-JPO-Stredocesky-kraj&category=integration)

Nebo ručně: **HACS → ⋮ → Custom repositories**, vlož
`https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj` a jako typ zvol **Integration**.
Pak integraci najdi v HACS, nainstaluj ji a restartuj Home Assistant.

### Ručně

1. Stáhni si poslední [release](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/releases).
2. Složku `custom_components/pkr_zasahy` zkopíruj do `/config/custom_components/`.
3. Restartuj Home Assistant.

## Nastavení

[![Přidat integraci](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pkr_zasahy)

1. Otevři **Nastavení → Zařízení a služby → Přidat integraci → Zásahy JPO**.
2. Vyber zdroj dat a nastav oblast podle pokynů níže.
3. Pro další oblast nebo druhý zdroj přidej další instanci integrace.

Název instance se doplní podle oblasti. Přes **Konfigurovat** nastavíš interval
kontroly: **5–60 minut**, výchozí je **10 minut**.

Existující PKR instance fungují bez nového nastavení a zachovají ID entit.

### Nastavení PKR

1. Na stránce zdroje v panelu **Filtr** vyber okres a případně stupeň poplachu.
2. Zkopíruj výslednou URL z prohlížeče.
3. V integraci vyber **Středočeský kraj (PKR)** a vlož adresu.

Předvyplněná URL je příklad filtru. Pro vlastní oblast ji nahraď adresou z webu.

### Nastavení Fire Brno

1. V integraci vyber **Fire Brno (HZS)**.
2. Vyber kraj z nabídky zdroje.
3. Vyber okres nebo ponech celý kraj. Kopírování URL není potřeba.
4. Volitelně do **Zasahující jednotka – vyhledat** zadej alespoň dva znaky názvu
   a v dalším kroku vyber jednotku z výsledků. Prázdné hledání nebo prázdný výběr
   zahrne všechny jednotky. Název můžeš vyhledat znovu přímo v kroku výběru.

Jednotka se kombinuje s filtrem kraje a okresu. Pokud chceš sledovat její zásahy
napříč okresy daného kraje, zvol celý kraj. Filtr jednotky platí pro všechny dostupné
senzory i eventy; název jednotky se přidá do názvu instance.
Existující instance zůstávají bez filtru jednotky. Pro sledování konkrétní jednotky
přidej novou instanci s tímto filtrem.

## Entity

Všechny instance mají pět společných senzorů; Fire Brno má navíc měsíční a roční přehled:

| Senzor | Stav | Atributy |
|---|---|---|
| Zásahy dnes | počet zásahů s dnešním datem podle času zdroje | `zasahy` |
| Probíhající zásahy | počet aktivních zásahů v dostupném rozsahu | `zasahy`; při neznámém stavu také `neznamy_stav` |
| Zásahy za poslední týden | počet zásahů v dostupné týdenní historii | `zasahy` |
| Poslední zásah | název nejnovějšího zásahu | pole posledního zásahu |
| Čas posledního zásahu | čas nejnovějšího zásahu, typ timestamp | – |
| Zásahy tento měsíc (Fire Brno) | počet zásahů od začátku aktuálního kalendářního měsíce | `zasahy`, informace o historii |
| Zásahy tento rok (Fire Brno) | počet zásahů od 1. ledna aktuálního roku | `zasahy`, informace o historii |

ID entit závisí na názvu instance, jazyku HA a případném ručním přejmenování.
Najdeš je u zařízení integrace nebo v **Vývojářské nástroje → Stavy**.
Do dashboardu vždy použij ID ze své instalace.

### Měsíční a roční historie (Fire Brno)

Oba přehledy používají čas ohlášení a kalendářní hranice v **Europe/Prague**,
nikoli posledních 30 nebo 365 dní. Mají stejný filtr kraje, okresu a jednotky jako
zbytek instance. PKR tyto senzory nevytváří, protože jeho tabulka úplnou historii neposkytuje.

Roční přehled se načte při startu a obnovuje jednou za místní kalendářní den.
Mezi obnovami se do paměťové kopie promítají aktuální záznamy z běžného pollingu.
Na začátku nového roku se načte nový roční přehled; měsíční senzor se automaticky
přepne na aktuální měsíc. Historické načítání ani opravy archivu nevyvolávají eventy.

Kromě úplného seznamu `zasahy` mají oba senzory atributy:

| Atribut | Význam |
|---|---|
| `od` / `do` | kalendářní začátek období a čas posledního běžného načtení |
| `historie_obnovena` | čas posledního úspěšného úplného načtení roční historie |
| `historie_zastarala` | `true`, pokud se úplné načtení nezdařilo nebo dosud chybí dnešní obnova |

Při prvním neúspěšném načtení historie jsou jen tyto dva senzory nedostupné;
ostatní senzory fungují dál. Pokud už existuje platná kopie pro aktuální rok,
zůstane dostupná s příznakem zastaralosti. Obnovení se pak zkouší nejvýše jednou
za hodinu. Paměťová kopie se po restartu znovu sestaví ze zdroje.
Seznamy `zasahy` se ani u těchto senzorů neukládají do recorderu.

### Společná pole zásahu

Položky v atributu `zasahy` a data eventů mají tato společná pole:

| Pole | Význam |
|---|---|
| `nazev` | název zásahu; u Fire Brno sestavený z kategorie, podtypu a obce |
| `kategorie` | například `požár`, `dopravní nehoda` nebo `technická pomoc` |
| `podtyp` | upřesnění události, například `odstranění stromu` |
| `typ` | typ události; u PKR podle ikony, u Fire Brno odpovídá kategorii |
| `stav` | textový stav ze zdroje |
| `aktivni` | `true` / `false`; u neznámého stavu Fire Brno `null` |
| `obec` | obec události |
| `okres` | okres; může být `null`, pokud ho zdroj u záznamu neuvádí |
| `stupen` | PKR: `I.`, `II.`, `III.` nebo `Z`; Fire Brno: `null` |
| `cas` | ISO 8601 s časovým pásmem; význam závisí na zdroji, viz tabulka níže |
| `id` | PKR: identifikátor řádku; Fire Brno: stabilní `firebrno:<id>` |

### Rozdíly mezi zdroji

| Vlastnost | PKR | Fire Brno |
|---|---|---|
| Význam `cas` | poslední aktualizace dat | čas ohlášení |
| Dnešní a poslední zásah | podle času aktualizace | podle času ohlášení |
| Týdenní přehled | seznam z webu, přibližně poslední týden | posledních 7 dní |
| Měsíční a roční přehled | není k dispozici | aktuální kalendářní měsíc a rok |
| Probíhající zásahy | z dostupného seznamu webu | kontrolované do 30 dní od ohlášení |
| Stupeň poplachu | poskytuje ho zdroj | v používaném seznamu není dostupný |
| Rozpoznání aktualizace | stejný název a obec, novější čas do 6 hodin | stejné nativní ID a změna obsahu, i bez změny času |

Fire Brno navíc poskytuje `provider`, `native_id`, `stav_id`, `cas_ohlaseni`,
`cas_vzniku`, `kraj`, `cast_obce`, `orp`, `ulice`, `silnice` a `poznamka`.
Volitelná pole mohou být `null`. `cas_aktualizace` je `null`, protože backend
čas poslední změny neposkytuje. Kategorie a podtypy jsou převedené na malá písmena.

## Eventy

Názvy eventů jsou společné pro všechny zdroje:

| Event | Kdy se vyšle | Pole navíc |
|---|---|---|
| `pkr_zasahy_novy_zasah` | objeví se nový zásah | `entry_id`, `provider`, `source_url` |
| `pkr_zasahy_aktualizace_zasahu` | změní se známý zásah podle pravidel zdroje | `entry_id`, `provider`, `source_url`, `predchozi_stav` |

`provider` je `pkr` nebo `firebrno`. `entry_id` označuje konkrétní instanci.
`source_url` vede na nakonfigurovaný přehled PKR nebo na hlavní stránku Fire Brno.

Pokud máš překrývající se instance, každá posílá vlastní eventy.
V automatizaci je můžeš rozlišit podle `entry_id` nebo `provider`.

## Příklady

Příklady fungují s oběma zdroji. Nahraď názvy obcí, notifikační službu a ID senzorů
hodnotami ze své instalace.

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
      {{ trigger.event.data.obec in ['Vaše obec', 'Sousední obec'] }}
actions:
  - action: notify.mobile_app_telefon
    data:
      title: >
        🚒 {{ trigger.event.data.kategorie | capitalize }} – {{ trigger.event.data.obec }}
      message: >
        {{ trigger.event.data.podtyp }} · {{ trigger.event.data.stav }}
        {% if trigger.event.data.stupen %} · stupeň {{ trigger.event.data.stupen }}{% endif %}
        {% if trigger.event.data.get('poznamka') %} · {{ trigger.event.data.poznamka }}{% endif %}
      data:
        url: "{{ trigger.event.data.source_url }}"
```

Další užitečné podmínky:

```jinja
{{ trigger.event.data.kategorie == 'požár' }}       {# jen požáry #}
{{ trigger.event.data.provider == 'firebrno' }}     {# jen zvolený zdroj #}
{{ trigger.event.data.entry_id == 'ID_VASI_INSTANCE' }}  {# jen konkrétní instance #}
{{ trigger.event.data.stupen in ['II.', 'III.', 'Z'] }}  {# vyšší stupeň, pouze PKR #}
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
      data:
        url: "{{ trigger.event.data.source_url }}"
```

Používej `aktivni == false`, aby se neznámý stav (`null`) nepovažoval za ukončení.
Event aktualizace může přijít i při jiné změně již ukončeného zásahu.

### Karta do dashboardu

V příkladu nahraď `sensor.vase_zasahy_za_posledni_tyden` skutečným ID týdenního
senzoru vybrané instance.

```yaml
type: markdown
title: 🚒 Zásahy v okolí
content: |
  {% set z = state_attr('sensor.vase_zasahy_za_posledni_tyden', 'zasahy') or [] %}
  | Čas | Událost | Obec | Stav |
  |---|---|---|---|
  {% for i in z[:10] -%}
  | {{ as_timestamp(i.cas) | timestamp_custom('%d.%m. %H:%M') }} | {{ i.kategorie }} – {{ i.podtyp }} | {{ i.obec }} | {{ '❔' if i.aktivni is none else '🔴' if i.aktivni else '⚪' }} {{ i.stav }} |
  {% endfor %}
```

## Jak to funguje

Každý zdroj má vlastní provider pro načtení a zpracování dat. Společný coordinator
zajišťuje pravidelné aktualizace, porovnání zásahů a eventy. Senzory čtou společný
formát dat. První úspěšné načtení po startu pouze naplní paměť.

PKR provider čte HTML tabulku. Fire Brno provider používá nedokumentovaný JSON
backend webové aplikace a denní paměťovou kopii číselníků. Neznámý kód vyvolá
nejvýše jeden dodatečný pokus o jejich obnovení denně. Platnou kopii lze použít
i při výpadku obnovení.

Fire Brno pro běžné senzory a eventy načítá sedmidenní historii a starší záznamy
do 30 dní, aby zachytilo
i ukončení již sledovaných zásahů. Zmizelý záznam se automaticky neoznačuje jako ukončený.
Chyba HTTP, JSON nebo struktury dat nastaví senzory jako nedostupné;
není považována za prázdný seznam.

## Omezení

- **Data jsou orientační a mohou být zpožděná.** Dostupnost a úplnost závisí na zdroji.
- **Časy mají podle zdroje jiný význam.** PKR ukazuje aktualizaci, Fire Brno ohlášení.
  „Poslední zásah“ proto u Fire Brno neznamená naposledy změněný zásah.
- **Rozsah závisí na zdroji a senzoru.** PKR poskytuje přibližně poslední týden.
  Fire Brno má týdenní, měsíční a roční přehled; senzor probíhajících zásahů
  kontroluje jen záznamy do 30 dní od ohlášení. Úplnost historie ani případné
  serverové omezení počtu záznamů nelze z nedokumentovaného backendu zaručit.
  Starší opravy se v měsíčním a ročním přehledu projeví až při úplné obnově.
- **Stav určuje provider.** U Fire Brno je rozhodující číselný kód. Kód `500` web
  řadí mezi otevřené, i když jeho text zní „Ukončená“. Neznámý kód má `aktivni: null`;
  počet probíhajících zásahů pak bude `unknown` s atributem `neznamy_stav`.
- **Některá pole jsou volitelná.** Například stupeň poplachu Fire Brno neposkytuje.
  Automatizace musí počítat s chybějícími nebo `null` hodnotami.
- **Změna webu nebo backendu může vyžadovat opravu provideru.** Při neočekávané
  struktuře dat budou senzory nedostupné. Problém nahlas v
  [issues](https://github.com/VAdamec/Zasahy-JPO-Stredocesky-kraj/issues).
- **Interval kontroly je nejméně 5 minut.** Výchozích 10 minut omezuje zatížení zdrojů.

## Vývoj

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests
.venv/bin/ruff check custom_components tests
```

Providery jsou v `custom_components/pkr_zasahy/providers/`, společný model
a porovnání v `models.py`, sdílené chování v `coordinator.py` a `sensor.py`.

`tests/test_parser.py` testuje PKR parser na uložené kopii stránky a nepotřebuje
Home Assistant, stačí `pytest`. Fire Brno testy používají syntetické JSON fixtures
odpovídající ověřenému schématu. Integrační testy pokrývají nastavení, senzory,
staré konfigurace, výpadky, restart, eventy a kalendářní historii včetně přelomu měsíce a roku. Automatické testy nepřistupují k živým zdrojům.

Logování pro ladění:

```yaml
logger:
  logs:
    custom_components.pkr_zasahy: debug
```

## Upozornění

Neoficiální projekt bez vazby na provozovatele zdrojů a HZS ČR.
Na notifikace z této integrace nespoléhej v situacích, kde jde o bezpečnost.
Data patří jejich provozovatelům.

## Licence

[MIT](LICENSE)
