from io import BytesIO, StringIO
from ruamel.yaml import YAML

yaml = YAML(typ='safe', pure=True)

def wrap(spec_file):
    data = yaml.load(spec_file)

    steps = data['steps'].keys()
    for s in steps:
        # add extra output fields for the whole workflow
        data['outputs'] += [
            {
                'id': f"{s}_metadata",
                'outputSource': f"{s}/metadata",
                'type': 'File'
            },
            {
                'id': f"{s}_out",
                'outputSource': f"{s}/out",
                'type': 'File'
            },
            {
                'id': f"{s}_err",
                'outputSource': f"{s}/err",
                'type': 'File'
            }
        ]
        # add extra output fields for every step
        data['steps'][s]['out'] += ['out','err','metadata']
        data['steps'][s]['requirements'] = {'InlineJavascriptRequirement': {}}

        data['steps'][s]['run']['outputs'] += [
            {
                'id': 'metadata',
                'outputBinding': {'glob': 'execution_metadata', "outputEval": "${\n    var output = self[0];\n    output.basename = 'metadata_%s';\n    return output;\n}" % s},
                'type': 'File'
            },

            {
                'id': 'out',
                'outputBinding': {'glob': 'stdout', "outputEval": "${\n    var output = self[0];\n    output.basename = 'stdout_%s';\n    return output;\n}" % s},
                'type': 'File'
            },
            {
                'id': 'err',
                'outputBinding': {'glob': 'stderr', "outputEval": "${\n    var output = self[0];\n    output.basename = 'stderr_%s';\n    return output;\n}" % s},
                'type': 'File'

            }
        ]

        prev_base_command = data['steps'][s]['run']['baseCommand']
        data['steps'][s]['run']["baseCommand"] = 'python'
        data['steps'][s]['run']["arguments"] = ['/app/execute_and_monitor.py', prev_base_command] + data['steps'][s]['run']["arguments"]


    with BytesIO() as output_yaml:
        yaml.dump(data, output_yaml)
        return output_yaml.getvalue()