"""Shared incident model and comparison, independent of Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha1


class ParseError(Exception):
    """Stránka nemá očekávanou strukturu (změnil se web nebo přišla chyba)."""


@dataclass(frozen=True)
class Zasah:
    """Jeden řádek tabulky zásahů."""

    nazev: str
    kategorie: str
    podtyp: str
    typ: str
    stav: str
    obec: str
    okres: str | None
    stupen: str | None
    cas: datetime
    provider: str = "pkr"
    native_id: int | None = None
    stav_id: int | None = None
    active_state: bool | None = None
    cas_ohlaseni: datetime | None = None
    cas_vzniku: datetime | None = None
    kraj: str | None = None
    cast_obce: str | None = None
    orp: str | None = None
    ulice: str | None = None
    silnice: str | None = None
    poznamka: str | None = None

    @property
    def klic(self) -> str:
        """Identita události bez času (čas se mění s aktualizací dat)."""
        if self.native_id is not None:
            return f"{self.provider}:{self.native_id}"
        return f"{self.nazev}|{self.obec}"

    @property
    def uid(self) -> str:
        """Identita konkrétního řádku včetně času poslední aktualizace."""
        if self.native_id is not None:
            return self.klic
        raw = f"{self.klic}|{self.cas.isoformat()}"
        return sha1(raw.encode()).hexdigest()[:12]

    @property
    def aktivni(self) -> bool | None:
        if self.native_id is not None:
            return self.active_state
        return not self.stav.lower().startswith("ukon")

    def as_dict(self) -> dict:
        data = {
            "nazev": self.nazev,
            "kategorie": self.kategorie,
            "podtyp": self.podtyp,
            "typ": self.typ,
            "stav": self.stav,
            "aktivni": self.aktivni,
            "obec": self.obec,
            "okres": self.okres,
            "stupen": self.stupen,
            "cas": self.cas.isoformat(),
            "id": self.uid,
        }

        if self.native_id is not None:
            data.update(
                {
                    "provider": self.provider,
                    "native_id": self.native_id,
                    "stav_id": self.stav_id,
                    "cas_ohlaseni": self.cas_ohlaseni.isoformat()
                    if self.cas_ohlaseni
                    else None,
                    "cas_vzniku": self.cas_vzniku.isoformat()
                    if self.cas_vzniku
                    else None,
                    "cas_aktualizace": None,
                    "kraj": self.kraj,
                    "cast_obce": self.cast_obce,
                    "orp": self.orp,
                    "ulice": self.ulice,
                    "silnice": self.silnice,
                    "poznamka": self.poznamka,
                }
            )
        return data


# Za jak dlouho po předchozím čase ještě bereme řádek se stejným názvem
# a obcí jako aktualizaci téže události (ne jako nový výjezd).
AKTUALIZACE_OKNO = timedelta(hours=6)


def rozdil(
    zname: dict[str, Zasah], aktualni: list[Zasah]
) -> tuple[list[Zasah], list[tuple[Zasah, Zasah]]]:
    """Porovná známé a aktuální řádky.

    Vrací (nove, aktualizovane), kde aktualizovane jsou dvojice (predchozi, nova).
    Aktualizace = stejná událost, které se změnil čas poslední aktualizace
    (typicky změna stavu probíhá -> ukončená).
    """
    aktualni_uid = {z.uid for z in aktualni}
    nove: list[Zasah] = []
    aktualizovane: list[tuple[Zasah, Zasah]] = []

    for z in sorted(aktualni, key=lambda x: x.cas):
        if z.native_id is not None:
            previous = zname.get(z.uid)
            if previous is None:
                nove.append(z)
            elif previous != z:
                aktualizovane.append((previous, z))
            continue
        if z.uid in zname:
            continue
        kandidati = [
            k
            for k in zname.values()
            if k.klic == z.klic
            and k.uid not in aktualni_uid
            and timedelta(0) <= z.cas - k.cas <= AKTUALIZACE_OKNO
        ]
        if kandidati:
            aktualizovane.append((max(kandidati, key=lambda k: k.cas), z))
        else:
            nove.append(z)
    return nove, aktualizovane


@dataclass(frozen=True)
class PeriodHistory:
    """Full current-year base plus recent merges; None means never loaded."""

    zasahy: list[Zasah] | None
    as_of: datetime
    refreshed: datetime | None = None
    stale: bool = False
