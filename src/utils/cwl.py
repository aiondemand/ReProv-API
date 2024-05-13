from io import BytesIO
import requests
from ruamel.yaml import YAML

yaml = YAML(typ='safe', pure=True)


def add_mapping_step(spec_file):
    data = yaml.load(spec_file)

    steps_file_outputs = {}
    for s in data['steps']:
        file_ouputs = {}
        outputs = data['steps'][s]['run']['outputs']
        for o in outputs:
            if o['type'] == 'File':
                file_ouputs[o['id']] = o['outputBinding']['glob']

        steps_file_outputs.update(file_ouputs)

    map_step_in = {}
    for s in steps_file_outputs:
        s_name = steps_file_outputs[s].split('.')[-1].rstrip(')')
        map_step_in[s_name] = s_name

    map_step_out = ['mapping']
    map_step_run_inputs = {}
    for s in steps_file_outputs:
        s_name = steps_file_outputs[s].split('.')[-1].rstrip(')')
        map_step_run_inputs[s_name] = 'string'

    map_step = {}
    map_step['in'] = map_step_in
    map_step['out'] = map_step_out
    map_step['run'] = {}
    map_step['run']['inputs'] = map_step_run_inputs
    map_step['run']['outputs'] = [
        {
            'id': 'mapping', 'outputBinding': {'glob': 'map.txt'},
            'type': 'File'
        }
    ]
    map_step['run']['class'] = 'CommandLineTool'
    map_step['run']['baseCommand'] = 'sh'

    mapping = {
        s: f"$(inputs.{map_step_in[steps_file_outputs[s].split('.')[-1].rstrip(')')]}"
        for s in steps_file_outputs
    }
    args = ''
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
    if 'requirements' not in data.keys():
        data['requirements'] = {}
    data['requirements']['InlineJavascriptRequirement'] = {}

    with BytesIO() as output_yaml:
        yaml.dump(data, output_yaml)
        return output_yaml.getvalue()


# function that replaces placeholders in the specification file.
# returns the new specification file and the entities that need to be retrieved
def replace_placeholders(spec_file):
    entities = []
    spec_file_yaml = yaml.load(spec_file)
    for i in spec_file_yaml['inputs']:
        if 'valueFromPlatform' in i.keys():

            dataset_url = i['valueFromPlatform'].strip('{}')
            url = f"{dataset_url}?schema=aiod"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                return None, None

            data = response.json()
            entities.append(
                {
                    'id': i['id'],
                    'type': 'aiod-platform',
                    'data': data
                }
            )
            del i['valueFromPlatform']  # delete it from cwl

            for s in spec_file_yaml['steps']:
                spec_file_yaml['steps'][s]['requirements'] = {}
                spec_file_yaml['steps'][s]['requirements'] = {
                    "InitialWorkDirRequirement": {
                        "listing": []
                    }
                }
                if i['id'] in spec_file_yaml['steps'][s]['in']:
                    spec_file_yaml['steps'][s]['requirements']['InitialWorkDirRequirement']['listing'].append(f"$(inputs.{i['id']})")

    with BytesIO() as output_yaml:
        yaml.dump(spec_file_yaml, output_yaml)
        return output_yaml.getvalue(), entities