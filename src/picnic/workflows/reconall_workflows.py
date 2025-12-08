# =======================================
# Imports
import os
import copy
from pathlib import Path

from nipype import Function
from nipype.interfaces.utility import Select, Merge

from picnic.workflows.custom_workflow_constructors import NipibipyWorkflow
from picnic.interfaces.io_nodes import _rename_image, _pop_list
from picnic.interfaces.string_template_nodes import _fill_report_template
from picnic.interfaces.nibabel_nodes import (
    _reorient_image,
    _create_bilateral_atlas,
    _create_atlas_sidecar,
    _binarize_images,
    _generate_wholebrain_mask,
    _generate_gray_matter_mask,
    _generate_white_matter_mask,
    _generate_subcortical_mask,
    _generate_ventricle_mask
)


# =======================================
# Constants
FREESURFER_OUTFLOWS_TO_EXPOSE = (
    'T1',
    'aseg',
    'brainmask',
    'wmparc'
)
DETERMINISTIC_ATLASES = (
    'wmparc',
)
LOOKUPTABLE_PATH = os.path.join(
    Path(__file__).parent.absolute(),
    'default_jsons',
    'freesurfer_lookuptable.json'
)
REPORT_TEMPLATE_PATH = os.path.join(
    Path(__file__).parent.absolute(),
    'report_templates',
    'reconall_template.html'
)

# =======================================
# Classes
class ReconallWorkflow:
    """ A parent class to all the individual reconall statuses. Most of the 
    steps will be the same across all types of this module (running/finding 
    freesurfer subject, reorienting important images, generate reports) This 
    creates a parent class keep the same steps, but overload the critical 
    "execute_reconall" method.
    
    The public attributes that are important:
    wf - the nipype.Workflow
    """
    DEFAULT_INFLOWS = {
        'subject_id': None,
        't1s': [],
        't2': None,
        'flair': None,
        'filepath': None
    }
    
    def __init__(self, params, inflows, verbose=False):
        """
        Parameters
        ----------
        params - dict
            key/value pairs of the keyword's optional parameters. See the 
            above DEFAULT_PARAMS constant for a list of all available keys
        inflows - dict
            the inflows to the workflow, {"inflow name" : file-like str}. See 
            the above DEFAULT_INFLOWS constant for a list of available keys
        """
        self.params = params
        self.inflows = copy.deepcopy(self.DEFAULT_INFLOWS)
        self.inflows.update(inflows)
        self.verbose = verbose
    
    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, all_paras):
        # remove the leading underscore for all parameters that have them
        parameters = {}
        for parameter_name, parameter_value in all_paras.items():
            if parameter_name.startswith('_'):
                parameter_name = parameter_name[1:]
            parameters[parameter_name] = parameter_value

        self._params = parameters

    def build_workflow(self, sink_directory):
        """ create a nipype workflow to run freesurfer's reconall
        
        Parameters
        ----------
        sink_directory - file-like str
            The sink filepath or ''
        
        returns - custom_workflow_constructors.NipibipyWorkflow obj
        """
        self.wf = NipibipyWorkflow(
            name = self.params['name'],
            outflows = {},
            sink_directory = sink_directory
        )
        
        # the workflow steps
        self.execute_reconall()
        self.reorient_outflows()
        self.generate_bilateral_rois()
        self.generate_wholebrain_mask()
        self.generate_gray_matter_mask()
        self.generate_white_matter_mask()
        self.generate_subcortical_mask()
        self.generate_ventricle_mask()
        if self.params['report']:
            self.create_report()
        
        return self.wf
    
    def execute_reconall(self):
        """ this will be overloaded by all its children
        """

        if self.verbose:
            print("ERROR: ")
            print("ERROR: This 'ReconallWorkflow::execute_reconall' ")
            print("ERROR: should have been overloaded and never run.")
            print("ERROR: ")

    def reorient_outflows(self):
        """ combine all the reoriented images to one volume and rename the file
        """
        # create an iterable connection for all outflows
        if self.verbose:
            for idx, a in enumerate(FREESURFER_OUTFLOWS_TO_EXPOSE):
                print(f"  - inflow - 'in{str(idx + 1)}': '@execute_reconall.{a}'")
        self.wf.add_node(
            interface = Merge(len(FREESURFER_OUTFLOWS_TO_EXPOSE)),
            name = 'merge_outflows_to_expose',
            inflows = dict(
                [['in' + str(idx + 1), '@execute_reconall.' + a]
                 for idx, a in enumerate(FREESURFER_OUTFLOWS_TO_EXPOSE)]
            ),
            outflows = (
                'out',
            ),
        )
        
        # reorient all the outflows
        self.wf.add_mapnode(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'new_image_path'
                ],
                function = _reorient_image
            ),
            name = 'reorient_outflows',
            inflows = {
                'in_file' : '@merge_outflows_to_expose'
            },
            outflows = (
                'new_image_path',
            ),
            iterfield = [
                'in_file'
            ]
        )
        
        # standardize the file name that was just merged/selected
        self.wf.add_mapnode(
            interface = Function(
                input_names = [
                    'basename',
                    'in_file'
                ],
                output_names = [
                    'new_image_path'
                ],
                function = _rename_image
            ),
            name = 'standardized_filenames',
            inflows = {
                'basename' : FREESURFER_OUTFLOWS_TO_EXPOSE,
                'in_file' : '@reorient_outflows'
            },
            outflows = (
                'new_image_path',
            ),
            iterfield = [
                'basename',
                'in_file'
            ],
            to_sink = [
                'new_image_path'
            ]
        ) 
    
    def generate_bilateral_rois(self):
        """
        Using a lookup table (defined as a static file in the nipibipy's
        sub-package) create a bilateral atlas and associated json for the 
        pre-determined atlases
        """

        for atlas in DETERMINISTIC_ATLASES:
            # select the atlas from the renamed niftis
            self.wf.add_node(
                interface = Select(),
                name = 'select_' + atlas,
                inflows = {
                    'inlist' : '@standardized_filenames',
                    'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index(atlas)
                },
                outflows = (
                    'out',
                )
            )
            
            # create a bilateral atlas based on that selected file and atlas
            #  and a freesurfer lookup table
            self.wf.add_node(
                interface = Function(
                    input_names = [
                        'atlas',
                        'lookup_table'
                    ],
                    output_names = [
                        'bilateral_out_file',
                        'json_out_file'
                    ],
                    function = _create_bilateral_atlas
                ),
                name = 'create_bilateral_' + atlas,
                inflows = {
                    'atlas' : '@select_' + atlas,
                    'lookup_table' : LOOKUPTABLE_PATH
                },
                outflows = (
                    'bilateral_out_file',
                    'json_out_file'
                ),
                to_sink = [
                    'bilateral_out_file',
                    'json_out_file'
                ]
            )

            # create a json sidecar for the original (non-bilateral) atlas
            # this provides label_lookup for TACs extraction
            self.wf.add_node(
                interface = Function(
                    input_names = [
                        'atlas',
                        'lookup_table'
                    ],
                    output_names = [
                        'json_out_file'
                    ],
                    function = _create_atlas_sidecar
                ),
                name = 'create_sidecar_' + atlas,
                inflows = {
                    'atlas' : '@select_' + atlas,
                    'lookup_table' : LOOKUPTABLE_PATH
                },
                outflows = (
                    'json_out_file',
                ),
                to_sink = [
                    'json_out_file'
                ]
            )

    def generate_wholebrain_mask(self):
        """ create a whole brain mask from the aseg
        """
        # select the atlas from the renamed niftis
        self.wf.add_node(
            interface = Select(),
            name = 'select_aseg_for_wholebrain',
            inflows = {
                'inlist' : '@standardized_filenames',
                'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index('aseg')
            },
            outflows = (
                'out',
            )
        )
        
        # create wholebrain mask
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'out_file'
                ],
                function = _generate_wholebrain_mask
            ),
            name = 'create_wholebrain_mask',
            inflows = {
                'in_file' : '@select_aseg_for_wholebrain'
            },
            outflows = (
                'mask_path',
            ),
            to_sink = [
                'out_file'
            ]
        )

    def generate_gray_matter_mask(self):
        """ create the gray matter mask by including some rois from the aseg
        """
        # select the atlas from the renamed niftis
        self.wf.add_node(
            interface = Select(),
            name = 'select_aseg_for_gray_matter',
            inflows = {
                'inlist' : '@standardized_filenames',
                'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index('aseg')
            },
            outflows = (
                'out',
            )
        )

        # create gray matter mask
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'out_file'
                ],
                function = _generate_gray_matter_mask
            ),
            name = 'create_gray_matter_mask',
            inflows = {
                'in_file' : '@select_aseg_for_gray_matter'
            },
            outflows = (
                'mask_path',
            ),
            to_sink = [
                'out_file'
            ]
        )

    def generate_white_matter_mask(self):
        """ create the white matter mask by including some rois from the aseg
        """
        # select the atlas from the renamed niftis
        self.wf.add_node(
            interface = Select(),
            name = 'select_aseg_for_white_matter',
            inflows = {
                'inlist' : '@standardized_filenames',
                'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index('aseg')
            },
            outflows = (
                'out',
            )
        )
        
        # create white matter mask
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'out_file'
                ],
                function = _generate_white_matter_mask
            ),
            name = 'create_white_matter_mask',
            inflows = {
                'in_file' : '@select_aseg_for_white_matter'
            },
            outflows = (
                'mask_path',
            ),
            to_sink = [
                'out_file'
            ]
        )
    
    def generate_subcortical_mask(self):
        """ create the white matter mask by including some rois from the aseg
        """
        # select the atlas from the renamed niftis
        self.wf.add_node(
            interface = Select(),
            name = 'select_aseg_for_subcortical',
            inflows = {
                'inlist' : '@standardized_filenames',
                'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index('aseg')
            },
            outflows = (
                'out',
            )
        )
        
        # create subcortical mask
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'out_file'
                ],
                function = _generate_subcortical_mask
            ),
            name = 'create_subcortical_mask',
            inflows = {
                'in_file' : '@select_aseg_for_subcortical'
            },
            outflows = (
                'mask_path',
            ),
            to_sink = [
                'out_file'
            ]
        )

    def generate_ventricle_mask(self):
        """ create the white matter mask by including some rois from the aseg
        """
        # select the atlas from the renamed niftis
        self.wf.add_node(
            interface = Select(),
            name = 'select_aseg_for_ventricle',
            inflows = {
                'inlist' : '@standardized_filenames',
                'index' : FREESURFER_OUTFLOWS_TO_EXPOSE.index('aseg')
            },
            outflows = (
                'out',
            )
        )
        
        # create ventricle mask
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'in_file'
                ],
                output_names = [
                    'out_file'
                ],
                function = _generate_ventricle_mask
            ),
            name = 'create_ventricle_mask',
            inflows = {
                'in_file' : '@select_aseg_for_ventricle'
            },
            outflows = (
                'mask_path',
            ),
            to_sink = [
                'out_file'
            ]
        )
    
    def create_report(self):
        """ create a report
        """
        self.wf.add_node(
            interface = Function(
                input_names = [
                    'html_template',
                    'parameters'
                ],
                output_names = [
                    'html'
                ],
                function = _fill_report_template
            ),
            name = 'report_template',
            inflows = {
                'html_template' : REPORT_TEMPLATE_PATH,
                'parameters' : self.params
            },
            outflows = (
                'html',
            ),
            to_sink = [
                'html'
            ]
        )
    
class ExecuteReconallWorkflow(ReconallWorkflow):
    """ execute freesurfer's reconall
    """
    def __init__(self, params, inflows):
        """
        Parameters
        ----------
        params - dict
            key/value pairs of the keyword's optional parameters.
        inflows - list
            list of file-like strs
        """
        params['type'] = 'execute'
        super().__init__(params, {})

        # If the card name is bidsy, find the sub-NAME, otherwise, use as is
        try:
            subject_id = {
                k.split('-')[0]: k
                for k in self.params['name'].split('_')
            }['sub'].split('-')[1]
        except KeyError:
            subject_id = self.params.get('name', "_")

        self.inflows['subject_id'] = subject_id
        if self.params['execution_type'] == 't1-only':
            self.inflows['t1s'] = inflows['in_files']
        elif self.params['execution_type'] == 't2':
            self.inflows['t1s'] = inflows['in_files'][:-1]
            self.inflows['t2'] = inflows['in_files'][-1]
        elif self.params['execution_type'] == 'flair':
            self.inflows['t1s'] = inflows['in_files'][:-1]
            self.inflows['flair'] = inflows['in_files'][-1]
    
    def execute_reconall(self):
        """ use Freesurfer to run reconall using nipype's Freesurfer interface
        
        Parameters
        ----------
        """

        from nipype.interfaces.freesurfer import ReconAll


        # use reconall
        if self.params['execution_type'] == 't1-only':
            self.wf.add_node(
                interface = ReconAll(),
                name = 'execute_reconall',
                inflows = {
                    'subject_id': self.inflows['subject_id'],
                    'T1_files': self.inflows['t1s'],
                },
                outflows = FREESURFER_OUTFLOWS_TO_EXPOSE
            )
            print(f"  - t1-only inflow - 'subject_id': '{self.inflows['subject_id']}'")
            print(f"  - t1-only inflow - 'T1_files': '{self.inflows['t1s']}'")
        elif self.params['execution_type'] == 't2':
            self.wf.add_node(
                interface = ReconAll(),
                name = 'execute_reconall',
                inflows = {
                    'subject_id': self.inflows['subject_id'],
                    'T1_files' : self.inflows['t1s'],
                    'T2_file' : self.inflows['t2'],
                    'use_T2' : True
                },
                outflows = FREESURFER_OUTFLOWS_TO_EXPOSE
            )
            if self.verbose:
                print(f"  - t2 inflow - 'subject_id': '{self.inflows['subject_id']}'")
                print(f"  - t2 inflow - 'T1_files': '{self.inflows['t1s']}'")
                print(f"  - t2 inflow - 'T2_file': '{self.inflows['t2']}'")
                print(f"  - t2 inflow - 'use_T2': '{True}'")
        elif self.params['execution_type'] == 'flair':
            self.wf.add_node(
                interface = ReconAll(),
                name = 'execute_reconall',
                inflows = {
                    'subject_id': self.inflows['subject_id'],
                    'T1_files' : self.inflows['t1s'],
                    'FLAIR_file' : self.inflows['flair'],
                    'use_FLAIR' : True
                },
                outflows = FREESURFER_OUTFLOWS_TO_EXPOSE
            )
            if self.verbose:
                print(f"  - flair inflow - 'subject_id': '{self.inflows['subject_id']}'")
                print(f"  - flair inflow - 'T1_files': '{self.inflows['t1s']}'")
                print(f"  - flair inflow - 'FLAIR_file': '{self.inflows['flair']}'")
                print(f"  - flair inflow - 'use_FLAIR': '{True}'")

class ReadReconallWorkflow(ReconallWorkflow):
    """ read a freesurfer directory using nipype's FreeSurferSource 
    """
    def __init__(self, params, inflows):
        """
        Parameters
        ----------
        params - dict
            key/value pairs of the keyword's optional parameters.
        inflows - list
            list of file-like strs
        """
        params['type'] = 'read existing'
        super().__init__(params, {'filepath' : inflows[0]})
    
    def execute_reconall(self):
        """ use nipype's FreeSurferSource to read an existing reconall
        
        Parameters
        ----------
        """

        import os
        from nipype.interfaces.io import FreeSurferSource

        
        # Break up provided filepath into freesurfer subject id/dir
        p = os.path.split(self.inflows['filepath'])
        
        # read existing reconall
        self.wf.add_node(
            interface = FreeSurferSource(),
            name = 'execute_reconall',
            inflows = {
                'subject_id' : p[1],
                'subjects_dir' : p[0]
            },
            outflows = FREESURFER_OUTFLOWS_TO_EXPOSE
        )
