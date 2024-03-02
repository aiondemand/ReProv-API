from io import BytesIO, StringIO
from ruamel.yaml import YAML

yaml = YAML(typ='safe', pure=True)

def wrap(spec_file):
    data = yaml.load(spec_file)

    steps_file_outputs = {}
    for s in data['steps']:
        file_ouputs = {}
        outputs = data['steps'][s]['run']['outputs']
        for o in outputs:
            if o['type'] == 'File':
                file_ouputs[o['id']] = o['outputBinding']['glob']

        steps_file_outputs.update(file_ouputs)

    # we are adding a final step in order to create a file that maps produced files with their corresponding name
    map_step_in = {}
    for s in steps_file_outputs:
        map_step_in[steps_file_outputs[s].split('.')[-1].rstrip(')')] = steps_file_outputs[s].split('.')[-1].rstrip(')')

    map_step_out = ['mapping']


    map_step_run_inputs = {}
    for s in steps_file_outputs:
        map_step_run_inputs[steps_file_outputs[s].split('.')[-1].rstrip(')')] = 'string'


    map_step = {}
    map_step['in'] = map_step_in
    map_step['out'] = map_step_out
    map_step['run'] = {}
    map_step['run']['inputs'] = map_step_run_inputs
    map_step['run']['outputs'] = [{'id': 'mapping', 'outputBinding': {'glob': 'map.txt'}, 'type':'File'}]
    map_step['run']['class'] = 'CommandLineTool'
    map_step['run']['baseCommand'] = 'sh'


    mapping = {
        s:f"$(inputs.{map_step_in[steps_file_outputs[s].split('.')[-1].rstrip(')')]}"
        for s in steps_file_outputs
    }
    args = f""""""
    for m in mapping:
        args += f"""
        echo {m},{mapping[m]}) >> map.txt  
        """

    map_step['run']['arguments'] = ["-c"] + [args]
    data['steps']['map'] = map_step


    data['outputs'] += [
        {
            'id': 'mapping',
            'outputSource': 'map/mapping',
            'type': 'File',
        }
    ]
    data['requirements']['InlineJavascriptRequirement'] =  {}


    with BytesIO() as output_yaml:
        yaml.dump(data, output_yaml)
        return output_yaml.getvalue()