# Befundlogik

**Prüfbare Regeln für Laborwerte als offener Baustein.**

Laborwerte entscheiden mit, wie schnell jemand behandelt wird. Deshalb laufen in Kliniken
Regeln, die gefährliche Konstellationen melden. Diese Regeln sind heute Betriebsgeheimnis
oder Insellösung: Jedes Haus baut sie neu, niemand von außen kann prüfen, ob sie stimmen,
und wenn eine Regel falsch meldet, merkt es im besten Fall die Ärztin, die sie wegklickt.

Befundlogik macht die Regel selbst zum prüfbaren Artefakt. Eine Regel führt mit:

1. **Eingangsgrößen** mit LOINC-Code und Einheit,
2. **Referenzbereiche** als Funktion von Alter und Geschlecht, nicht als Konstante,
3. **Begründung** mit Literaturverweis,
4. **Testfälle** mit erwartetem Ergebnis, die zur Regel gehören und mitlaufen.

Daraus folgt das Wichtigste: **Fehlt der Referenzbereich für eine Patientengruppe,
verweigert die Regel das Urteil.** Sie wendet nicht stillschweigend den
Erwachsenenbereich auf ein Kind an.

> **Stand: Prinzipbeweis.** Dieses Repository zeigt die Struktur an einer
> Beispielregel, ohne FHIR-Anbindung und ohne echte Klinikdaten. Der produktive Teil —
> Regelschema als `Pydantic`-Modell, Einheiten über `pint`/UCUM, z(log)-Transformation,
> FHIR-Ein- und Ausgabe, eigenschaftsbasierte Prüfung mit `Hypothesis` — ist Gegenstand
> der Bewerbung beim Prototype Fund, Jahrgang 03.

## Ausprobieren

Keine Abhängigkeiten, Python 3.11 genügt:

```
python3 befundlogik.py            # Vorführung
python3 befundlogik.py --selftest # Tests
```

## Was die Vorführung zeigt

Ausgabe eines echten Durchlaufs (14.10.2026):

```
Regel: entzuendungskonstellation v0.1.0
  CRP und Leukozyten gemeinsam über dem Referenzbereich — Hinweis auf eine akute Entzündung, prüfbedürftig.
  Quelle: Beispielregel für den Prinzipbeweis; produktiv aus publizierter Literatur
  Braucht: 1988-5, 6690-2 (LOINC)

Erwachsene, CRP 80 mg/l, Leuko 15/nl
  -> AUFFÄLLIG
     1988-5 = 80 mg/l über dem Bereich 0–5
     6690-2 = 15 /nl über dem Bereich 4–10
     Grundlage: Beispielregel für den Prinzipbeweis; produktiv aus publizierter Literatur

Dieselbe Patientin, Werte in mg/dl und /µl geliefert
  -> AUFFÄLLIG
     1988-5 = 80 mg/l über dem Bereich 0–5
     6690-2 = 15 /nl über dem Bereich 4–10
     Grundlage: Beispielregel für den Prinzipbeweis; produktiv aus publizierter Literatur

Kind, 7 Jahre, gleiche Werte
  -> UNBESTIMMT
     kein Referenzbereich für 6690-2 bei Alter 7, Geschlecht m — die Regel ist hier nicht zuständig

Mitgelieferte Testfälle: 6, alle bestanden
```

Drei Dinge sind daran wesentlich:

- **Jeder Befund nennt seine Gründe.** Nicht „auffällig", sondern welcher Wert welchen
  Bereich verlässt — und die Quelle der Regel. Eine Warnung, die man nicht nachvollziehen
  kann, wird weggeklickt, und das zu Recht.
- **Einheiten sind kein Formatproblem.** `80 mg/l` und `8 mg/dl` sind derselbe Wert. Die
  Regel urteilt identisch, inklusive identischer Begründung. Eine Regel, die das nicht
  mitführt, ist beim Umzug in ein anderes Labor stillschweigend falsch.
- **Die Regel kennt ihre Grenze.** Für Kinder ist im Beispiel absichtlich kein
  Leukozyten-Referenzbereich hinterlegt. Das Ergebnis ist `UNBESTIMMT` mit Begründung,
  nicht ein geratenes Urteil.

## Eine Regel definieren

```python
ENTZUENDUNG = Regel(
    name="entzuendungskonstellation",
    version="0.1.0",
    beschreibung="CRP und Leukozyten gemeinsam über dem Referenzbereich …",
    quelle="…Literaturverweis…",
    benoetigt=(CRP, LEUKOZYTEN),
    bereiche=(
        Bereich(CRP, "mg/l", 0.0, 5.0, ab_alter=18),
        Bereich(LEUKOZYTEN, "/nl", 4.0, 10.0, ab_alter=18),
    ),
    testfaelle=(
        Testfall("erwachsen, beide erhöht", …, erwartet=Urteil.AUFFAELLIG),
        Testfall("Kind — Referenzbereich fehlt", …, erwartet=Urteil.UNBESTIMMT),
    ),
)
```

`regel.teste_dich_selbst()` führt die mitgelieferten Fälle aus. Wer die Regel in sein Haus
übernimmt, kann vorher prüfen, ob sie auf den eigenen Daten das tut, was sie behauptet.

## Herkunft

Von 2019 bis 2022 war ich am Universitätsklinikum Leipzig für die KI-Entwicklung des
klinischen Entscheidungssystems **AMPEL** verantwortlich, das Laborbefunde auf gefährliche
Konstellationen prüft (u. a. *JMIR Medical Informatics* 9.6, 2021).

Die öffentliche Projektgruppe [ampel-leipzig](https://github.com/ampel-leipzig) enthält
R-Forschungspakete zu einzelnen Modellen — die **Regelschicht selbst ist nicht
veröffentlicht**, und sie gehört dem Klinikum. Befundlogik ist deshalb von außen und neu
geschrieben; übernommen wird nur die Erfahrung, an welcher Stelle eine Regel beim Umzug in
ein anderes Labor falsch wird.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
