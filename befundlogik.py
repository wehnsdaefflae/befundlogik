"""befundlogik — Prinzipbeweis: eine Laborregel, die ihre eigene Prüfbarkeit mitführt.

Eine Regel ist hier kein Stück Code, das irgendwo im Laborinformationssystem steckt,
sondern ein Objekt mit vier Teilen:

1. **Eingangsgrößen** mit LOINC-Code und Einheit — damit dieselbe Regel in mmol/l und
   mg/dl dasselbe tut.
2. **Referenzbereiche** als Funktion von Alter und Geschlecht, nicht als Konstante.
3. **Begründung** mit Literaturverweis.
4. **Testfälle** mit erwartetem Ergebnis, die zur Regel gehören und mitlaufen.

Der wichtigste Punkt ist der fünfte, der sich daraus ergibt: Fehlt der Referenzbereich für
eine Patientengruppe, **verweigert die Regel das Urteil** (`UNBESTIMMT`), statt den
Erwachsenenbereich stillschweigend auf ein Kind anzuwenden. Ein Werkzeug, das in der
Medizin Vertrauen verdienen soll, muss sagen können, dass es nicht zuständig ist.

Ausführen:   python3 befundlogik.py
Tests:       python3 befundlogik.py --selftest
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum

# --- Einheiten -------------------------------------------------------------------
# Umrechnungsfaktoren auf eine Basiseinheit je Messgröße. Im produktiven Entwurf
# macht das `pint` gegen UCUM; hier genügt eine Tabelle, um das Prinzip zu zeigen.

FAKTOREN: dict[tuple[str, str], float] = {
    ("mg/l", "mg/l"): 1.0,
    ("mg/dl", "mg/l"): 10.0,      # 1 mg/dl = 10 mg/l
    ("g/l", "g/l"): 1.0,
    ("g/dl", "g/l"): 10.0,
    ("/nl", "/nl"): 1.0,
    ("/µl", "/nl"): 0.001,        # 1000/µl = 1/nl
}


class Urteil(Enum):
    UNAUFFAELLIG = "unauffällig"
    AUFFAELLIG = "auffällig"
    UNBESTIMMT = "unbestimmt"     # Voraussetzungen der Regel nicht erfüllt


@dataclass(frozen=True)
class Messwert:
    loinc: str
    wert: float
    einheit: str


@dataclass(frozen=True)
class Patient:
    alter_jahre: float
    geschlecht: str               # "w", "m", "d"


@dataclass(frozen=True)
class Bereich:
    """Ein Referenzbereich, gültig für eine Alters- und Geschlechtsgruppe."""

    loinc: str
    einheit: str
    unten: float
    oben: float
    ab_alter: float = 0.0
    bis_alter: float = 200.0
    geschlecht: str | None = None  # None = alle

    def passt(self, p: Patient) -> bool:
        if not (self.ab_alter <= p.alter_jahre < self.bis_alter):
            return False
        return self.geschlecht is None or self.geschlecht == p.geschlecht


@dataclass(frozen=True)
class Testfall:
    name: str
    werte: tuple[Messwert, ...]
    patient: Patient
    erwartet: Urteil


@dataclass
class Befund:
    urteil: Urteil
    begruendung: list[str] = field(default_factory=list)
    regel: str = ""
    version: str = ""


@dataclass
class Regel:
    """Eine Regel mit Herkunft, Begründungspflicht und eigenen Testfällen."""

    name: str
    version: str
    beschreibung: str
    quelle: str                              # Literaturverweis
    benoetigt: tuple[str, ...]               # LOINC-Codes
    bereiche: tuple[Bereich, ...]
    testfaelle: tuple[Testfall, ...] = ()

    # --- Einheiten ---
    def _normiere(self, m: Messwert, ziel: str) -> float:
        schluessel = (m.einheit, ziel)
        if schluessel not in FAKTOREN:
            raise ValueError(f"keine Umrechnung {m.einheit} → {ziel}")
        return m.wert * FAKTOREN[schluessel]

    def _bereich_fuer(self, loinc: str, p: Patient) -> Bereich | None:
        for b in self.bereiche:
            if b.loinc == loinc and b.passt(p):
                return b
        return None

    def pruefe(self, werte: tuple[Messwert, ...], p: Patient) -> Befund:
        vorhanden = {m.loinc: m for m in werte}

        fehlend = [c for c in self.benoetigt if c not in vorhanden]
        if fehlend:
            return Befund(Urteil.UNBESTIMMT,
                          [f"Messwert fehlt: {', '.join(fehlend)}"],
                          self.name, self.version)

        auffaellig: list[str] = []
        for code in self.benoetigt:
            m = vorhanden[code]
            b = self._bereich_fuer(code, p)
            if b is None:
                return Befund(
                    Urteil.UNBESTIMMT,
                    [f"kein Referenzbereich für {code} bei Alter "
                     f"{p.alter_jahre:g}, Geschlecht {p.geschlecht} — "
                     f"die Regel ist hier nicht zuständig"],
                    self.name, self.version)
            wert = self._normiere(m, b.einheit)
            if wert > b.oben:
                auffaellig.append(
                    f"{code} = {wert:g} {b.einheit} über dem Bereich "
                    f"{b.unten:g}–{b.oben:g}")
            elif wert < b.unten:
                auffaellig.append(
                    f"{code} = {wert:g} {b.einheit} unter dem Bereich "
                    f"{b.unten:g}–{b.oben:g}")

        if len(auffaellig) == len(self.benoetigt):
            return Befund(Urteil.AUFFAELLIG,
                          auffaellig + [f"Grundlage: {self.quelle}"],
                          self.name, self.version)
        return Befund(Urteil.UNAUFFAELLIG,
                      auffaellig or ["alle Werte im Referenzbereich"],
                      self.name, self.version)

    def teste_dich_selbst(self) -> list[str]:
        """Führt die mitgelieferten Testfälle aus. Leere Liste = alles bestanden."""
        fehler = []
        for t in self.testfaelle:
            got = self.pruefe(t.werte, t.patient).urteil
            if got is not t.erwartet:
                fehler.append(f"{self.name}/{t.name}: erwartet "
                              f"{t.erwartet.value}, war {got.value}")
        return fehler


# --- Eine Beispielregel. Bewusst einfach: zwei Entzündungsmarker gemeinsam erhöht. ---
# Die Schwellen stehen hier als Referenzbereiche; die echte Regel aus der Literatur
# arbeitet mit Verläufen. Für den Prinzipbeweis zählt die Struktur, nicht die Medizin.

CRP = "1988-5"          # LOINC: C-reaktives Protein
LEUKOZYTEN = "6690-2"   # LOINC: Leukozyten

ENTZUENDUNG = Regel(
    name="entzuendungskonstellation",
    version="0.1.0",
    beschreibung=("CRP und Leukozyten gemeinsam über dem Referenzbereich — "
                  "Hinweis auf eine akute Entzündung, prüfbedürftig."),
    quelle="Beispielregel für den Prinzipbeweis; produktiv aus publizierter Literatur",
    benoetigt=(CRP, LEUKOZYTEN),
    bereiche=(
        # Erwachsene
        Bereich(CRP, "mg/l", 0.0, 5.0, ab_alter=18),
        Bereich(LEUKOZYTEN, "/nl", 4.0, 10.0, ab_alter=18),
        # Kinder: nur CRP hinterlegt — Leukozyten fehlen absichtlich,
        # um die Verweigerung zu zeigen.
        Bereich(CRP, "mg/l", 0.0, 5.0, ab_alter=0, bis_alter=18),
    ),
    testfaelle=(
        Testfall("erwachsen, beide erhöht",
                 (Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
                 Patient(45, "w"), Urteil.AUFFAELLIG),
        Testfall("erwachsen, beide normal",
                 (Messwert(CRP, 2.0, "mg/l"), Messwert(LEUKOZYTEN, 6.0, "/nl")),
                 Patient(45, "w"), Urteil.UNAUFFAELLIG),
        Testfall("erwachsen, nur CRP erhöht",
                 (Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 6.0, "/nl")),
                 Patient(45, "w"), Urteil.UNAUFFAELLIG),
        Testfall("dieselben Werte in mg/dl und /µl",
                 (Messwert(CRP, 8.0, "mg/dl"), Messwert(LEUKOZYTEN, 15000.0, "/µl")),
                 Patient(45, "w"), Urteil.AUFFAELLIG),
        Testfall("Kind — Referenzbereich fehlt",
                 (Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
                 Patient(7, "m"), Urteil.UNBESTIMMT),
        Testfall("Leukozyten nicht gemessen",
                 (Messwert(CRP, 80.0, "mg/l"),),
                 Patient(45, "w"), Urteil.UNBESTIMMT),
    ),
)


def vorfuehrung() -> int:
    r = ENTZUENDUNG
    print(f"Regel: {r.name} v{r.version}")
    print(f"  {r.beschreibung}")
    print(f"  Quelle: {r.quelle}")
    print(f"  Braucht: {', '.join(r.benoetigt)} (LOINC)")
    print()

    faelle = [
        ("Erwachsene, CRP 80 mg/l, Leuko 15/nl",
         (Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
         Patient(45, "w")),
        ("Dieselbe Patientin, Werte in mg/dl und /µl geliefert",
         (Messwert(CRP, 8.0, "mg/dl"), Messwert(LEUKOZYTEN, 15000.0, "/µl")),
         Patient(45, "w")),
        ("Kind, 7 Jahre, gleiche Werte",
         (Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
         Patient(7, "m")),
    ]

    for titel, werte, p in faelle:
        b = r.pruefe(werte, p)
        print(f"{titel}")
        print(f"  -> {b.urteil.value.upper()}")
        for z in b.begruendung:
            print(f"     {z}")
        print()

    print("Die zweite Zeile zeigt die Einheitenumrechnung: identisches Urteil.")
    print("Die dritte zeigt die Verweigerung: für Kinder ist kein Leukozyten-Bereich")
    print("hinterlegt, also urteilt die Regel nicht — statt den Erwachsenenbereich")
    print("stillschweigend anzuwenden.")
    print()

    fehler = r.teste_dich_selbst()
    print(f"Mitgelieferte Testfälle: {len(r.testfaelle)}, "
          f"{'alle bestanden' if not fehler else f'{len(fehler)} fehlgeschlagen'}")
    for f in fehler:
        print(f"  {f}")
    return 1 if fehler else 0


def selftest() -> int:
    ok = True

    def expect(c: bool, m: str) -> None:
        nonlocal ok
        if not c:
            ok = False
            print(f"FAIL: {m}", file=sys.stderr)

    r = ENTZUENDUNG
    expect(r.teste_dich_selbst() == [], "die Regel besteht ihre eigenen Testfälle")

    # Einheitenumrechnung ist nicht nur gleich im Urteil, sondern im Wert
    b1 = r.pruefe((Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
                  Patient(45, "w"))
    b2 = r.pruefe((Messwert(CRP, 8.0, "mg/dl"), Messwert(LEUKOZYTEN, 15000.0, "/µl")),
                  Patient(45, "w"))
    expect(b1.urteil is b2.urteil is Urteil.AUFFAELLIG, "mg/dl == mg/l im Urteil")
    expect(b1.begruendung == b2.begruendung, "auch die Begründung ist identisch")

    # Verweigerung statt Raten
    kind = r.pruefe((Messwert(CRP, 80.0, "mg/l"), Messwert(LEUKOZYTEN, 15.0, "/nl")),
                    Patient(7, "m"))
    expect(kind.urteil is Urteil.UNBESTIMMT, "Kind ohne Bereich: unbestimmt")
    expect("nicht zuständig" in " ".join(kind.begruendung),
           "die Verweigerung wird begründet")

    # Jeder Befund trägt Regelname und Version
    expect(b1.regel == "entzuendungskonstellation" and b1.version == "0.1.0",
           "Befund nennt Regel und Version")

    # Unbekannte Einheit fällt auf, statt falsch zu rechnen
    try:
        r.pruefe((Messwert(CRP, 1.0, "furlong"), Messwert(LEUKOZYTEN, 6.0, "/nl")),
                 Patient(45, "w"))
        expect(False, "unbekannte Einheit muss auffallen")
    except ValueError:
        pass

    # Grenzwert genau auf der Schwelle gilt als unauffällig
    rand = r.pruefe((Messwert(CRP, 5.0, "mg/l"), Messwert(LEUKOZYTEN, 10.0, "/nl")),
                    Patient(45, "w"))
    expect(rand.urteil is Urteil.UNAUFFAELLIG, "Wert auf der Obergrenze ist im Bereich")

    print("selftest: PASS" if ok else "selftest: FAIL", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else vorfuehrung())
