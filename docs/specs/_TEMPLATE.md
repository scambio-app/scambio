# Spec NN — Titolo

Stato: bozza | approvata | consegnata | verificata · Autore: Claude · Data:

## 1. Obiettivo

Cosa cambia per l'utente e come lo si vede (la prova visibile).

## 2. Decisioni applicabili

Voci di `docs/decisions.md` e misure di `docs/hardware-lab.md` su cui si basa.

## 3. Dettagli

### 3.1 Comportamento
### 3.2 API D-Bus, configurazione, dati
### 3.3 Interfaccia (riferimenti a `design/` e al contratto di `05-ui-context.md`)
### 3.4 Errori e casi limite

## 4. Fuori scope

## 5. Dipendenze

## 6. Checklist di done

- [ ] Ogni regola di §3.1 ha un test (unit della macchina a stati o integrazione con dbusmock).
- [ ] `make check` verde; nessun test saltato.
- [ ] Nessun polling introdotto; misura CPU/RSS a riposo (10 min) nel report.
- [ ] Nessun valore personale hardcodato; nuove chiavi di configurazione documentate in 02.
- [ ] Testi nuovi solo tramite chiavi del contratto (it/en/de).
- [ ] `design/` non modificato; richieste di design elencate nel report.
- [ ] `docs/verification/NN/report.md` scritto; decisioni tecniche in `docs/decisions.md`.
- [ ] Checklist di prova reale per GM preparata (dispositivo, telefono, desktop).
- [ ] Prova reale eseguita da GM: … · Firma: GM, data.

## 7. Note di revisione (Claude, dopo la consegna)

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

## 9. Domande aperte

## Comando `/goal`

```
/goal Implementa docs/specs/NN-nome.md seguendo AGENTS.md e docs/context/. Fatto solo quando
ogni voce della Checklist di done è soddisfatta con evidenza e `make check` è verde. Scope: solo
§3; §4 non si tocca; design/ non si modifica. Stop: se la spec contraddice AGENTS.md o manca una
decisione di prodotto, fermati e scrivilo nel report.
```
