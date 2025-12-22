# =======================================
# Imports

# =======================================
# Constants

# =======================================
# Classes

# =======================================
# Functions

# =======================================
# Nipype Specific Functions
def _reorient_image(in_file, gz=True):
    """
    use nibabel to load an imaging file type and save it as a nifti1

    :Parameters:
      -. `in_file` : file-like str, the file name
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import nibabel as nib
    from nibabel.orientations import OrientationError
    from picnic.interfaces.utility import nibabel_image_types


    # Open the image with nibabel
    base_name = ""
    dirname, filename = os.path.split(in_file)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            base_name = filename.replace(img_type, '')
            break
    orig_image = nib.load(in_file)
    if orig_image is None:
        print(f"SHIT! Failed to load '{in_file}' - orig_image is None")
    else:
        print(f"Loaded image for reorientation, shaped {orig_image.shape}")

    # grab the important image parameters
    # TODO: Eric reports that having a non-diagonal affine breaks FLIRT.
    #       I'm sure he's right, but I can't find any information, so I'll see what happens.
    #       The best approach to fix this is probably to apply the non-diagonal
    #       affine, then resample back?
    try:
        reoriented_image = nib.funcs.as_closest_canonical(orig_image, enforce_diag=True)
    except OrientationError:
        print("WARNING!")
        print(f"WARNING! The image '{in_file}' has a non-diagonal affine.")
        print(f"WARNING! We are hacking up a new fake diagonal affine.")
        print("WARNING!")
        affine = orig_image.affine
        ornt, flip = [], []
        for idx in range(3):
            v = affine[idx, :3]
            v_hat = v / (v ** 2).sum() ** 0.5

            ornt.append(list(v_hat).index(max(v_hat, key=abs)))
            flip.append(int(round(v_hat.sum(), 0)))
        reoriented_image = orig_image.as_reoriented([[a, flip[a]] for a in ornt])

    # save out the new image
    if gz:
        new_image_path = os.path.join(os.getcwd(), f"{base_name}_reoriented.nii.gz")
    else:
        new_image_path = os.path.join(os.getcwd(), f"{base_name}_reoriented.nii")
    print(f"Saving reoriented image as '{new_image_path}'")
    nib.save(reoriented_image, new_image_path)
    
    return new_image_path


""" While this function DOES work, it is suggested the user utilize the nibabel 
    function nibabel.func.as_closest_canonical(). They give the same results, 
    but nibabel's is faster and better tested
"""
def _reorient_image_deprecated(in_file, gz=True):
    """
    use nibabel to load an imaging file type and save it as a nifti1
    
    :Parameters:
      -. `in_file` : file-like str, the file name
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types

    # open the image with nibabel
    dirname, filename = os.path.split(in_file)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    image = nib.load(in_file)
    
    # grab the important image parameters
    affine = image.affine
    ornt, flip = [], []
    for idx in range(3):
        v = affine[idx, :3]
        v_hat = v / (v**2).sum()**0.5
        
        ornt.append(list(v_hat).index(max(v_hat, key=abs)))
        flip.append(int(round(v_hat.sum(), 0)))
    reornt_image = image.as_reoriented([[a, flip[a]] for a in ornt])
    
    # save out the new image
    if gz:
        new_image_path = os.path.join(os.getcwd(), basename+'_reoriented.nii.gz')
    else:
        new_image_path = os.path.join(os.getcwd(), basename+'_reoriented.nii')
    nib.save(reornt_image, new_image_path)
    
    return new_image_path


def _merge_images(images, gz=True):
    """
    use nibabel to merge a group of images over the last axis (usually time)
    
    :Parameter:
      -. `images` : list of file-like str, all the images that will be merged
        along the last axis
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types


    # Open the image with nibabel
    dirname, filename = os.path.split(images[0])
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    
    # merge all the listed files
    merged_image = nib.funcs.concat_images(images, axis=-1)
    
    # save out the new image
    if gz:
        new_image_path = os.path.join(os.getcwd(), basename+'_merged.nii.gz')
    else:
        new_image_path = os.path.join(os.getcwd(), basename+'_merged.nii')
    nib.save(merged_image, new_image_path)
    
    return new_image_path


def _create_bilateral_atlas(atlas, lookup_table, gz=True):
    """
    A nipype function used to create a bilateral atlas for deterministic
    atlases.
    
    :Parameters:
      -. `atlas` : file-like str, a 3d deterministic atlas
      -. `lookup_table` : file-like str, a lookup table json file that
        associates index to label
    """

    import os
    import json
    import numpy as np
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types

    # use nibabel to load the 3d image
    dirname, filename = os.path.split(atlas)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    atlas = nib.load(atlas)
        
    
    # use the json package to load the lookup table
    with open(lookup_table) as f:
        label_lookup = json.load(f)['label_lookup']
        label_lookup = dict((int(k), v.lower()) for k, v in label_lookup.items())
    
    # get the unilateral atlas's data as integers and initialize the bilateral
    unilateral_fdata = atlas.get_fdata().astype(int)
    bilateral_fdata = np.zeros(unilateral_fdata.shape)
    bilateral_lookup = {}
    
    # (1) loop over all the unique integers in the atlas
    # (2) check if it has a hemisphere indicator in its label (left, right, etc)
    # (3) search for a corresponding counterpart in the lookup table
    # (4) assign both hemispheres to the first one's index in the new atlas
    # (5) if both hemispheres found, replace the label name with bilateral
    idx_added = []
    for roi_idx in np.unique(unilateral_fdata):
        roi_idx = int(roi_idx)
        # Because the opposite hemisphere gets assigned the first time its
        # counterpart is found, it needs to be skipped
        if roi_idx in idx_added:
            continue
        
        # Find the index's associated label
        idx_label = label_lookup[roi_idx]
        
        # Use np.where to find all the voxels with the index
        bilateral_fdata += np.where(unilateral_fdata == roi_idx, roi_idx, 0.)
        bilateral_lookup[roi_idx] = idx_label
        idx_added.append(roi_idx)
        
        # check if there is a opposing hemisphere in the lookup table
        for to_check, opp_check in zip(('left', 'lh', 'right', 'rh'), ('right', 'rh', 'left', 'lh')):
            if to_check in idx_label:
                try:
                    opp_label = idx_label.replace(to_check, opp_check)
                    opp_idx = list(label_lookup.keys())[list(label_lookup.values()).index(opp_label)]
                
                # found a potential tag (ex 'left') in the label string, but 
                #  couldn't find its partner ('right') in the lookup table
                except ValueError:
                    break
                
                # use np..where to find all the voxels with the other
                #  hemisphere's index and assign it as the original index's 
                #  index in the bilateral data
                bilateral_fdata += np.where(unilateral_fdata == opp_idx, roi_idx, 0.)
                bilateral_lookup[roi_idx] = idx_label.replace(to_check, 'bilateral') # overwrite bilateral label name to contain 'bilateral'
                idx_added.append(opp_idx)
    
    # save out the new image
    if gz:
        bilateral_out_file = os.path.join(os.getcwd(), 'bilateral_' + basename + '.nii.gz')
    else:
        bilateral_out_file = os.path.join(os.getcwd(), 'bilateral_' + basename + '.nii')
    nib.save(nib.Nifti1Image(bilateral_fdata, atlas.affine), bilateral_out_file)
    
    # save out the associated json
    out_json = {'label_lookup' : bilateral_lookup}
    json_out_file = os.path.join(os.getcwd(), 'bilateral_' + basename + '.json')
    with open(json_out_file, 'w') as f:
        json.dump(out_json, f, indent=4)
    
    return (bilateral_out_file, json_out_file)

def _create_atlas_sidecar(atlas, lookup_table):
    """
    Create a JSON sidecar file for an atlas using a lookup table.
    This provides label names for each ROI index in the atlas.

    :Parameters:
      -. `atlas` : file-like str, a 3d deterministic atlas
      -. `lookup_table` : file-like str, a lookup table json file that
        associates index to label
    """

    import os
    import json
    import numpy as np
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types

    # get the basename from the atlas filename
    dirname, filename = os.path.split(atlas)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break

    # load the atlas to get unique ROI indices
    atlas_img = nib.load(atlas)
    atlas_fdata = atlas_img.get_fdata().astype(int)
    unique_indices = np.unique(atlas_fdata)

    # load the lookup table
    with open(lookup_table) as f:
        full_lookup = json.load(f)['label_lookup']

    # create a filtered lookup containing only indices present in the atlas
    atlas_lookup = {}
    for roi_idx in unique_indices:
        roi_idx_str = str(int(roi_idx))
        if roi_idx_str in full_lookup:
            atlas_lookup[roi_idx_str] = full_lookup[roi_idx_str]

    # save out the json sidecar
    out_json = {'label_lookup': atlas_lookup}
    json_out_file = os.path.join(os.getcwd(), basename + '.json')
    with open(json_out_file, 'w') as f:
        json.dump(out_json, f, indent=4)

    return json_out_file

def _binarize_images(images, thr=None, uthr=None, gz=True):
    """
    force all non-zeros to 1. All images must be the same shape
    
    :Parameters:
      -. `images` : list of file-like paths or single file-like str, all the
        images to binarize
      -. `thr` : None or float, zero everything below the value
      -. `uthr` : None or float, zero everything above the value
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import numpy as np
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types

    # error check if the images parameter is a string or list
    if isinstance(images, str):
        images = [images]
    
    # get the first file's name
    dirname, filename = os.path.split(images[0])
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    
    # loop over all the provided images, binarize each one and sum those
    for img in images:
        # load the image and get its fdata
        image = nib.load(img)
        image_data = image.get_fdata()
        
        # test if a lower threshold was given
        if not thr is None:
            image_data = np.where(image_data >= thr, image_data, 0.)
        
        # test if an upper threshold was given
        if not uthr is None:
            image_data = np.where(image_data <= uthr, image_data, 0.)
        
        # if the remaining thresheld data is not 0, set it to one
        try:
            new_data += np.where(image_data != 0., 1., 0.)
        except NameError: # a cheaters way to initialize an array without setting zeros
            new_data = np.where(image_data != 0., 1., 0.)
    
    # binarize the summed data (if two files overlap, it might end up with a 2. 
    #  We don't want that)
    new_data = np.where(new_data > 0., 1., 0.)
    binarized_image = nib.Nifti1Image(new_data, image.affine)
    
    # save out the new image
    if gz:
        new_image_path = os.path.join(os.getcwd(), basename+'_binarized.nii.gz')
    else:
        new_image_path = os.path.join(os.getcwd(), basename+'_binarized.nii')
    nib.save(binarized_image, new_image_path)
    
    return new_image_path
    
def _crop_image(in_file, crop_start=0, crop_end=0, gz=True):
    """
    use nibabel to crop the start and/or end of an image
    
    :Parameters:
      -. `in_file` : file-like str, the 4d image
      -. `crop_start` : int, how many frames to crop out from the start
      -. `crop_end` : int, how many frames to crop out from the end
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types


    # Open the image with nibabel
    dirname, filename = os.path.split(in_file)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    image = nib.load(in_file)
    
    # use nibabel's slicer to change up the image
    if crop_end != 0:
        new_image = image.slicer[:, :, :, crop_start:crop_end]
    else:
        new_image = image.slicer[:, :, :, crop_start:]
    
    # save out the new image
    if gz:
        new_image_path = os.path.join(os.getcwd(), basename+'_cropped.nii.gz')
    else:
        new_image_path = os.path.join(os.getcwd(), basename+'_cropped.nii')
    nib.save(new_image, new_image_path)
    
    return new_image_path

def _resample_image(source, target, gz=True):
    """
    Use nibabel.processing.resmple_from_to to resample the source image to
    target image space
    
    :Parameters:
      -. `source` : file-like str, the image to be resampled
      -. `target` : file-like str, the target image
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """

    import os
    import nibabel as nib
    from nibabel.processing import resample_from_to
    from picnic.interfaces.utility import nibabel_image_types

    # open the image with nibabel
    dirname, filename = os.path.split(source)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    
    # load the source and target images
    s = nib.load(source)
    t = nib.load(target)
    out_image = resample_from_to(s, t)
    
    # save out the new image
    if gz:
        resampled_image = os.path.join(os.getcwd(), basename+'_resampled.nii.gz')
    else:
        resampled_image = os.path.join(os.getcwd(), basename+'_resampled.nii')
    nib.save(out_image, resampled_image)
    
    return resampled_image


def _create_tacs(source, atlases, source_side_car=None, atlas_side_cars=None, units='uci'):
    """
    A nipype function used to create a tacs file based on an atlas and 4d
    image. 
    (1) Load the source and atlas image
    (2) Force atlas to be 3d (it already should be)
    (3) Resample the source to be in atlas space
    (4) Load the atlas side car to get the roi labels
    (5) Loop over each unique index in the atlas to create a mask and apply 
        that to all frames of the source
    (6) Convert to mCi/mL
    (7) Load the source side car to determine the mid-times
    (8) Assemble the data in a 2d array and save as a tsv
    
    :Parameters:
      -. `source` : file-like str, the filename of the 4d source image
      -. `target` : file-like str, the filename of the target image
      -. `source_side_car` : file-like str, the filepath to the source's side
        car json
      -. `atlas_side_car` : file-like str, the filepath to the atlas' side car
        json
      -. `units` : str, available options are uci or bq
    """

    import os
    import json
    import numpy as np
    import pandas as pd
    import nibabel as nib
    from nilearn.image import resample_to_img
    from picnic.interfaces.utility import nibabel_image_types

    # read the basename
    dirname, filename = os.path.split(source)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    
    # load the 4d image
    source_image = nib.load(source)
    
    # read the midtimes where available. If not, use the index
    if source_side_car:
        with open(source_side_car) as f:
            data = json.load(f)
            midtimes = list(np.array(data["FrameTimesStart"]) + (np.array(data["FrameDuration"]) / 2.))
    else:
        midtimes = list(range(source_image.shape[3]))
    
    # loop over each atlas and extract tacs for each roi
    tacs, labels = [], []
    for idx, atlas in enumerate(atlases):
        # load the atlas image
        atlas_image = nib.load(atlas)
        
        # load the atlas sidecar
        try:
            atlas_side_car = atlas_side_cars[idx]
            with open(atlas_side_car) as f:
                label_lookup = json.load(f)['label_lookup']
                label_lookup = dict((k, v.lower()) for k, v in label_lookup.items())
        except TypeError:
            label_lookup = {}
        except IndexError:
            label_lookup = {}
        
        # resample the source image to atlas space
        resampled_source = resample_to_img(source_image, atlas_image)
        
        # load the voxel data as matrices
        source_fdata = resampled_source.get_fdata()
        atlas_fdata = atlas_image.get_fdata().astype(int)
        
        # loop over all the unique rois in the atlas
        for roi_idx in np.unique(atlas_fdata):
            # create a binary mask at the index
            roi_mask = np.where(atlas_fdata==roi_idx, 1., 0.)
            
            roi_tacs = []
            for frame in range(source_fdata.shape[3]):
                # apply the binary roi mask created above to the source image
                source_frame_mask = source_fdata[:,:,:,frame] * roi_mask
                
                mx = np.sum(source_frame_mask) / np.sum(roi_mask)
                roi_tacs.append(mx)
            tacs.append(roi_tacs)
            
            # find the roi's associated label
            try:
                label = label_lookup[str(roi_idx)]
            except KeyError:
                label = str(roi_idx)

            # force each label name to be unique
            if label in labels:
                label_idx = 1
                label_counter = label + str(label_idx)
                while label_counter in labels:
                    label_idx += 1
                    label_counter = label + str(label_idx)
                label = label_counter
            labels.append(label)
    
    # unit correct to uCi/mL
    if units == 'uci':
        tac_matrix = np.transpose(np.array(tacs)) * (1 / 37000.)
    else:
        tac_matrix = np.transpose(np.array(tacs))
    
    # save the tacs as a tsv using pandas
    tac_file = os.path.join(os.getcwd(), basename+'_tacs.tsv')
    df = pd.DataFrame(tac_matrix, columns=labels, index=midtimes)
    df.to_csv(tac_file, sep='\t')
    
    return tac_file



def _generate_wholebrain_mask(in_file, gz=True):
    """
    use nibabel to create a wholebrain mask starting from the aseg
    generated from freesurfer's reconall

    :Parameters:
      -. `in_file` : file-like str, the aseg file
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """
    import nibabel as nib
    import numpy as np
    import os

    # the exclusions used to translate aseg to wholebrain
    WB_EXCLUSIONS = [
        2,
        4,
        5,
        14,
        15,
        24,
        30,
        31,
        41,
        43,
        44,
        62,
        63,
        77,
        85,
        251,
        252,
        253,
        254,
        255
    ]

    # load the aseg atlas
    aseg_atlas = nib.load(in_file)
    aseg_fdata = aseg_atlas.get_fdata().astype(int)

    # create the wholebrain mask by exclusing certain rois
    wholebrain_mask = np.zeros(aseg_atlas.shape)
    wholebrain_mask += np.where(aseg_fdata > 0, 1., 0.)
    for roi in WB_EXCLUSIONS:
        wholebrain_mask -= np.where(aseg_fdata == roi, 1., 0.)
    
    # save out the new image
    if gz:
        mask_path = os.path.join(os.getcwd(), 'wholebrain_mask.nii.gz')
    else:
        mask_path = os.path.join(os.getcwd(), 'wholebrain_mask.nii')
    nib.save(
        nib.Nifti1Image(
            wholebrain_mask,
            aseg_atlas.affine
        ),
        mask_path
    )

    return mask_path

def _generate_gray_matter_mask(in_file, gz=True):
    """
    use nibabel to create a gray matter mask starting from the aseg
    generated from freesurfer's reconall

    :Parameters:
      -. `in_file` : file-like str, the aseg file
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """
    import nibabel as nib
    import numpy as np
    import os

    # the inclusions used to translate aseg to gray matter
    GM_INCLUSIONS = [
        3,
        8,
        42,
        47
    ]

    # load the aseg atlas
    aseg_atlas = nib.load(in_file)
    aseg_fdata = aseg_atlas.get_fdata().astype(int)
    
    # create the gray matter mask by exclusing certain rois
    gm_mask = np.zeros(aseg_atlas.shape)
    for roi in GM_INCLUSIONS:
        gm_mask += np.where(aseg_fdata == roi, 1., 0.)
    
    # save out the new image
    if gz:
        mask_path = os.path.join(os.getcwd(), 'gm_mask.nii.gz')
    else:
        mask_path = os.path.join(os.getcwd(), 'gm_mask.nii')
    nib.save(
        nib.Nifti1Image(
            gm_mask,
            aseg_atlas.affine
        ),
        mask_path
    )

    return mask_path

def _generate_white_matter_mask(in_file, gz=True):
    """
    use nibabel to create a gray matter mask starting from the aseg
    generated from freesurfer's reconall

    :Parameters:
      -. `in_file` : file-like str, the aseg file
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """
    import nibabel as nib
    import numpy as np
    import os

    # the inclusions used to translate aseg to white matter
    WM_INCLUSIONS = [
        2,
        7,
        41,
        46,
        251,
        252,
        253,
        254,
        255
    ]

    # load the aseg atlas
    aseg_atlas = nib.load(in_file)
    aseg_fdata = aseg_atlas.get_fdata().astype(int)

    # create the wholebrain mask by exclusing certain rois
    wm_mask = np.zeros(aseg_atlas.shape)
    for roi in WM_INCLUSIONS:
        wm_mask += np.where(aseg_fdata == roi, 1., 0.)

    # Save out the new image
    if gz:
        mask_path = os.path.join(os.getcwd(), 'wm_mask.nii.gz')
    else:
        mask_path = os.path.join(os.getcwd(), 'wm_mask.nii')
    nib.save(
        nib.Nifti1Image(
            wm_mask,
            aseg_atlas.affine
        ),
        mask_path
    )

    return mask_path

def _generate_subcortical_mask(in_file, gz=True):
    """
    Use nibabel to create a subcortical mask starting from the aseg
    generated from freesurfer's reconall

    :Parameters:
      -. `in_file` : file-like str, the aseg file
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """
    import nibabel as nib
    import numpy as np
    import os

    # the exclusions used to translate aseg to subcortical
    SUBCORTICAL_EXCLUSIONS = [
        2,
        3,
        4,
        5,
        14,
        15,
        24,
        30,
        31,
        41,
        42,
        43,
        44,
        62,
        63,
        77,
        85,
        251,
        252,
        253,
        254,
        255
    ]

    # load the aseg atlas
    aseg_atlas = nib.load(in_file)
    aseg_fdata = aseg_atlas.get_fdata().astype(int)

    # create the subcortical mask by exclusing certain rois
    subcortical_mask = np.zeros(aseg_atlas.shape)
    subcortical_mask += np.where(aseg_fdata > 0, 1., 0.)
    for roi in SUBCORTICAL_EXCLUSIONS:
        subcortical_mask -= np.where(aseg_fdata == roi, 1., 0.)
    
    # save out the new image
    if gz:
        mask_path = os.path.join(os.getcwd(), 'subcortical_mask.nii.gz')
    else:
        mask_path = os.path.join(os.getcwd(), 'subcortical_mask.nii')
    nib.save(
        nib.Nifti1Image(
            subcortical_mask,
            aseg_atlas.affine
        ),
        mask_path
    )

    return mask_path

def _generate_ventricle_mask(in_file, gz=True):
    """
    use nibabel to create a ventricle mask starting from the aseg
    generated from freesurfer's reconall

    :Parameters:
      -. `in_file` : file-like str, the aseg file
      -. `gz` : boolean, save the file as a nifti_gz (True) or nifti (False)
    """
    import nibabel as nib
    import numpy as np
    import os

    # the inclusions used to translate aseg to venticle
    VENTRICLE_INCLUSIONS = [
        4,
        5,
        14,
        15,
        24,
        43,
        44
    ]

    # load the aseg atlas
    aseg_atlas = nib.load(in_file)
    aseg_fdata = aseg_atlas.get_fdata().astype(int)

    # create the wholebrain mask by exclusing certain rois
    ventricle_mask = np.zeros(aseg_atlas.shape)
    for roi in VENTRICLE_INCLUSIONS:
        ventricle_mask += np.where(aseg_fdata == roi, 1., 0.)

    # Save out the new image
    if gz:
        mask_path = os.path.join(os.getcwd(), 'ventricle_mask.nii.gz')
    else:
        mask_path = os.path.join(os.getcwd(), 'ventricle_mask.nii')
    nib.save(
        nib.Nifti1Image(
            ventricle_mask,
            aseg_atlas.affine
        ),
        mask_path
    )

    return mask_path


'''
def find_linear_tail_tac_aberrations(image_4d, json=None):
    """ use nibabel to calculate the whole brain TAC and find which, if any, 
    frames deviant from the expected linear tail expectation.
    
    Parameter
    ---------
    image_4d - file-like str
        the 4d image from which a TAC will be extracted
    json - file-like str or None
        can be included to use time to better predict slopes
    """
    
    import os
    import numpy as np
    import nibabel as nib
    from picnic.interfaces.utility import nibabel_image_types
    
    # read the basename
    dirname, filename = os.path.split(image_4d)
    for img_type in nibabel_image_types:
        if filename.endswith(img_type):
            basename = filename.replace(img_type, '')
            break
    
    # load the 4d image
    im = nib.load(image_4d)
    tac = np.sum(im.get_fdata(), (0,1,2))
'''
