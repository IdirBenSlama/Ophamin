# Dataset card — The Well (physics-simulation HDF5)

## Source

- The Well (Polymathic AI): <https://polymathic-ai.org/the_well/>
- Curated collection of physics-simulation datasets in a unified
  HDF5 format.
- License: per-dataset (most CC-BY); see the project's
  [LICENSE](https://github.com/PolymathicAI/the_well) for details.

## Size

The Well aggregates many simulation datasets. Common ones used in
Kimera-SWM research (see Kimera CLAUDE.md Stage 03/04 references):

| Dataset | Approximate size |
|---|---|
| `turbulent_radiative_layer_2D` | ~2 GB |
| `shear_kelvin_helmholtz` | ~5 GB |
| `gravity_cooling` | ~3 GB |
| (others) | varies |

Each dataset is a series of timesteps of a physics field; each
timestep is a 2D or 3D float array.

## Schema (per record)

The Ophamin connector lifts a single timestep slice as one record:

| Field | Type | Description |
|---|---|---|
| `id` | str | `<dataset>/timestep_<N>` |
| `text` | str | (optional) caption / units / shape descriptor — fed to scenarios that expect text |
| `metadata.shape` | list[int] | array shape |
| `metadata.dataset` | str | parent dataset name |
| `metadata.timestep` | int | timestep index |

## Labels

No labels. The Well is used for physics-content stimuli — the
substrate's response to a physics field is the signal.

## Refresh

```bash
pip install -e ".[well]"   # installs h5py (the connector's only opt dep)
# datasets are downloaded on first access via the Polymathic loader API
```

## Used by

- Currently no Ophamin scenario uses The Well directly — the physics
  experiments live in the Kimera-SWM observatory tree (Stage 03 /
  Stage 04 / EV-29 cross-modal brutality).
- Future scenario candidates: a cross-modal-coherence scenario that
  fans the same physics field through Kimera's visual + text +
  cochlear arms.

## Optional dependency

The Well connector requires `h5py`; install with:

```bash
pip install -e ".[well]"
```

Without `h5py`, `TheWellCorpus.is_available()` returns False and
scenarios `pytest.skip(...)` cleanly.
