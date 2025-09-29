# PICNIC

## Run PICNIC in docker (easiest)

You need to have docker installed already, then you can download the docker
image and run it on your data. The major benefit of docker is that
Python, FSL, FreeSurfer, AFNI, Connectome Workbench, and PICNIC are
already installed inside the docker container, so you don't have to
deal with those dependencies on your own.

You can use a provided wrapper script for the simplest interface.
We have also provided an example input deck
(PICNIC/_sample_input_decks/example_ds004513_sub-s012.inp)
to process one subject from the downloadable
[The energetic costs of the human connectome](https://doi.org/10.18112/openneuro.ds004513.v1.0.0)
dataset. Edit the paths inside the input deck to reflect your system.

```bash
/path/to/picnic/scripts/run_picnic_in_docker \
  /path/to/input_deck.inp \
  /path/to/your/read_only_input_data \
  /path/to/write/picnic_results \
  /path/to/freesurfer/license.txt
```

Or you can use docker directly for more control.

```bash
docker pull mfschmidt/picnic:latest
docker run --rm \
  -v /path/to/your/data:/input:ro \
  -v /path/to/your/results:/output:rw \
  -v /path/to/your/input_deck.inp:/input_deck.inp:ro \
  -v /path/to/your/freesurfer/license.txt:/opt/freesurfer/license.txt:ro \
  mfschmidt/picnic:latest /input_deck.inp
```

## Run PICNIC directly

To run picnic directly, you don't need docker, but you do need to have all of
its dependencies already installed. We don't provide documentation for
dependencies, but you may find the `PICNIC/Dockerfile` useful as a recipe.

```bash
pip install -U git+git@github.com:bil-mind-nyspi/PICNIC.git
cd PICNIC
./src/picnic/run.py my_input_deck.inp
```
