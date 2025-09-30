---
title: 'PICNIC: an open-source Python library for preprocessing of dynamic Positron Emission Tomography (PET) brain imaging data'
tags:
  - Python
  - PET
  - brain imaging
  - pet preprocessing
  - open-source
  - PICNIC
authors:
  - name: Francesca Zanderigo
    orcid: 0000-0001-6510-0676
    affiliation: 1, 2
  - name: Eric Hauser
    affiliation: 1, 2
  - name: Mike Schmidt
    orcid: 0000-0003-4721-1457
    affiliation: 1, 2
  - name: Elizabeth A Bartlett
    orcid: 0000-0002-9174-9951
    affiliation: 1, 2
  - name: Jeffrey M Miller
    orcid: 0000-0002-2206-9311
    affiliation: 1, 2
affiliations:
 - name: Department of Psychiatry, Columbia University Medical Center, New York, NY, United States
   index: 1
 - name: Molecular Imaging and Neuropathology Area, New York State Psychiatric Institute, New York, NY, United States
   index: 2
date: 17 July 2025
bibliography: paper.bib

---

# Summary

PICNIC (Pipeline Initializing Container for Neuro-Imaging Computations) is an
open-source Python-based coding library that includes modular wrappers for most
standard preprocessing steps for quantification of Positron Emission Tomography (PET) brain imaging data.
PICNIC uniquely allows full, transparent modular control over the selection of
strategy/software package and associated parameters for each preprocessing step
throughout the pipeline. Therefore, the user is provided with the flexibility to
select different methods depending on the target of interest and/or radiotracer
properties, study population, or other preferences. These settings can be saved
as a text-based “input deck” file to support consistent preprocessing across
scans, participants, and projects. Furthermore, PICNIC supports freezing
software versions within Docker containers, ensuring robust reproducibility.

PICNIC does not require Brain Imaging Data Structure (BIDS) source-level data,
but instead takes reconstructed PET static or dynamic data in industry standard
imaging filetypes (e.g., DICOM, Nifti, ANALYZE), and converts them to be
BIDS-compliant [@Knudsen2020Guidelines]. PICNIC employs the most commonly used
brain imaging software packages, including Advanced Normalization Tools
[@Avants2008Symmetric], Analysis of Function NeuroImages [@Cox1996AFNI],
FSL [@Jenkinson2012Fsl], FreeSurfer [@Fischl2012FreeSurfer],
dcm2niix [@Li2016DICOM], and SPM [@SPM12].
PICNIC was designed with PET in mind, but includes steps involving data from
multiple imaging modalities, most prominently structural magnetic resonance
imaging (sMRI). PICNIC preprocessing capabilities include image reorientation
(to force all images into a standard orientation regardless of scanner defaults),
brain extraction (to perform skull-stripping of associated sMRI images),
tissue segmentation (to classify sMRI voxels within the brain boundary as grey
matter vs. white matter vs. cerebrospinal fluid),
automatic anatomical parcellation (to identify regions
of interest using any available atlas/parcellation), post-reconstruction
rigid-body motion-correction (to correct inter-frame participant motion over the
duration of the scan), PET-sMRI co-registration (with 20 different PET-sMRI
rigid-body transformations that are automatically ranked based on mutual
information), and extraction of time-activity-curves (curves that represent the
PET signal over the duration of the scan in delineated regions of interest or in
each brain voxel). 

PICNIC can be run from the command line or through the provided graphical user
interface. An html summary output with interactive quality control features
allows the user to inspect, comment, and approve/disapprove each module for each
participant upon completion. Pre-loaded templates have been provided for
commonly used workflows. The user can add, remove or edit pre-processing steps
to fully customize their pipeline with regards to their dataset. PICNIC
currently supports over 100,000 module/parameter combinations.

PICNIC is designed for in vivo brain investigations by expert PET researchers,
and has already been applied to preprocess data for recent scientific
publications from [our Lab](https://www.columbiapsychiatry.org/research-labs/brain-imaging-lab)
[@Graves2024Gut;@Bartlett2024TSPO;@Matheson2024Biologically;@Bartlett2024Dual;
@Bartlett2024Quantification;@Herzog2024ER176;@Bartlett2023Vivo;
@Bartlett2023Relationships;@Bartlett2023Investigation;@Mann2022Neuroinflammation;
@Miller2022Relationships;@Herzog2025Neuroinflammation]
(https://www.columbiapsychiatry.org/research-labs/brain-imaging-lab). PICNIC’s
modular nature enables extensive customization of preprocessing for a variety of
brain PET studies, and its design may allow future extension to preprocessing of
data from imaging modalities other than PET. The source code for PICNIC is
available at the following link: https://github.com/bil-mind-nyspi/PICNIC.

# Statement of need

PET is a valuable tool used in research and
clinical settings to noninvasively image the human brain in vivo. PET can
quantify up to nanomolar levels of specific components of brain metabolic and
neurochemical processes, thus providing information on the distribution of
specific biological targets, such as receptors and enzymes, or on the uptake of
specific compounds into the brain, like glucose and polyunsaturated fatty acids.
Rigorous preprocessing of the raw data captured by the PET scanner [@Norgaard2019Optimization]
is key to obtaining the most accurate estimates of the distribution of a biological 
target or uptake of a substance using PET. Although a few software packages already
exist [@Karjalainen2020Magia;@Funck2018APPIAN;@Routier2021Clinica]
that perform most of the required preprocessing steps, a fully
open-source library that can modularly and flexibly combine appropriate
preprocessing strategies depending on the study design at hand is still missing.

# References


