# pendulum-factory-python

The Python part of the MAS417 pendulum kit factory. It contains:
- the web interface (Flask);
- order processing;
- the Spoolman REST client;
- parametric CAD (CadQuery) and 3MF export;
- the mass and period calculations;
- the design solver.

It is normally used as the `python/` submodule of the main repository **pendulum-factory**. Start there for the full setup (Spoolman, C++ simulator). This README covers the Python part only.

## Install

Python 3.11 or 3.12 (3.13 is not supported by CadQuery).

```bash
python3.12 -m venv .venv          # Windows: py -3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Spoolman must be running (see the main repository). Then:

```bash
python scripts/seed_stock.py                    # load makerspace filaments into Spoolman (safe to repeat)
flask --app pendulum.app run --port 5050        # web interface at http://localhost:5050
python scripts/process_orders.py examples/orders   # process orders without the web interface
```

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `SPOOLMAN_URL` | `http://localhost:7912/api/v1` | Spoolman REST API |
| `PENDULUM_SIM` | searched in `../cpp/build/` | Path to the C++ simulator executable. If not found, the SciPy simulation is used |

| File | Meaning |
|---|---|
| `config/defaults.json` | Default dimensions and print settings |
| `config/printer.json` | Build volume of the makerspace printers |
| `config/stock_seed.json` | Filaments found in the makerspace (used by `seed_stock.py`) |

## Package layout

| Module | Owner | Responsibility |
|---|---|---|
| `pendulum/params.py` | Thomas | `PendulumParams`: the shared parameter description, save/load JSON, `validate()` |
| `pendulum/cad.py` | Thomas | Build the six parts with CadQuery, export one 3MF per part |
| `pendulum/physics.py` | Thomas | Mass from density, walls and infill; exact period; bisection design solver |
| `pendulum/simulate.py` | Thomas | Runs the C++ simulator, with SciPy fallback |
| `pendulum/stock.py` | Øivind | `SpoolmanClient`, spool selection |
| `pendulum/processing.py` | Øivind | `Order`, `process_order()`: from order to 3MF files and registered filament use |
| `pendulum/app.py` + `templates/` | Øivind | Flask pages: order form and operator page |
| `pendulum/variants.py` | Øivind | Design-variant comparison plots and slicer comparison |

## Conventions

- **Units:** JSON and CAD use mm and grams. Physics converts to SI (m, kg, s) internally.
- **One source of truth:** every produced order has one `design.json`. CAD, mass, period and simulation all read it.
- **Errors:** "Spoolman not answering" and "not enough filament" postpone an order. An impossible design rejects it. Both store the reason.

## Tests

```bash
pytest                    # unit tests (integration tests are skipped by default, see pytest.ini)
pytest -m integration     # only the tests against Spoolman; needs it running
```

## Licence and AI

Third-party libraries and licences are listed in the main repository README. AI-assisted code is marked with a comment. See `docs/ai-log.md` in the main repository.
