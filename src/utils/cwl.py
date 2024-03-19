from io import BytesIO
from ruamel.yaml import YAML
from schema.init_db import session
from schema.prov import Entity

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
    data = yaml.load(spec_file)
    for i in data['inputs']:
        if 'valueFromEntity' in i.keys():
            entity_id = i['valueFromEntity'].strip('{}')
            entity = session.query(Entity).filter(Entity.id == entity_id).first()
            if entity is None:
                return None

            entities.append(
                {
                    'id': i['id'],
                    'data': entity
                }
            )
            del i['valueFromEntity']  # delete it from cwl

    with BytesIO() as output_yaml:
        yaml.dump(data, output_yaml)
        return output_yaml.getvalue(), entities
