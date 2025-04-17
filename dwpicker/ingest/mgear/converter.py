import os
import json
import uuid
from dwpicker.pyside import QtGui
from dwpicker.ingest.mgear.template import (
    BACKGROUND, PICKER, SHAPE_BUTTON, COMMAND, MENU_COMMAND)
from dwpicker.shapepath import rotate_path


def image_to_background_shape(imagepath):
    shape = BACKGROUND.copy()
    shape['image.path'] = imagepath
    image = QtGui.QImage(imagepath)
    shape['image.width'] = image.size().width()
    shape['image.height'] = image.size().height()
    shape['shape.width'] = image.size().width()
    shape['shape.height'] = image.size().height()
    shape['bgcolor.transparency'] = 255
    shape['id'] = str(uuid.uuid4())
    return shape


def convert(filepath, directory=None):
    directory = directory or os.path.dirname(filepath)
    with open(filepath, 'r') as f:
        data = json.load(f)

    picker = {'general': PICKER.copy()}
    picker['general']['name'] = data['tabs'][0]['name']
    picker['general']['panels.colors'] = [None] * len(data['tabs'])
    picker['general']['panels.names'] = [tab['name'] for tab in data['tabs']]
    picker['general']['as_sub_tab'] = True
    picker['general']['panels'] = [[1.0, [1.0] * len(data['tabs'])]]

    picker['shapes'] = []
    if data['snapshot']:
        if not os.path.exists(data['snapshot']):
            print(
                'WARNING: Impossible to import background image: '
                f'{data["snapshot"]}, file does not exists')
        else:
            for i in range(len(data['tabs'])):
                background_shape = image_to_background_shape(data['snapshot'])
                background_shape['panel'] = i
                picker['shapes'].append(background_shape)

    for i, tab in enumerate(data['tabs']):
        for item in tab["data"]['items']:
            picker['shapes'].append(dwpicker_shape_from_mgear_item(item, i))

    name = os.path.splitext(os.path.basename(filepath))[0]
    dst = unique_filename(directory, name, 'json')
    with open(dst, 'w') as f:
        json.dump(picker, f, indent=2)
    return dst


def get_path_center(path):
    bb = [
        min((p['point'][0] for p in path)),
        min((p['point'][1] for p in path)),
        max((p['point'][0] for p in path)),
        max((p['point'][1] for p in path))]
    x = bb[0] + ((bb[2] - bb[0]) / 2)
    y = bb[1] + ((bb[3] - bb[1]) / 2)
    return x, y


def dwpicker_shape_from_mgear_item(item, panel):
    shape = SHAPE_BUTTON.copy()
    shape['id'] = str(uuid.uuid4())
    shape['panel'] = panel
    r, g, b = item.get('color', [0, 0, 0])[:3]
    shape['bgcolor.normal'] = f'#{r:02X}{g:02X}{b:02X}'
    shape['bgcolor.transparency'] = 255 - item.get('color', [0, 0, 0, 255])[-1]
    shape['bgcolor.hovered'] = lighter(shape['bgcolor.normal'], 50)
    shape['action.targets'] = item.get('controls', [])
    shape['shape.left'] = item.get('position', [0, 0])[0]
    shape['shape.top'] = -item.get('position', [0, 0])[1]
    shape['text.content'] = item.get('text', '')
    shape['text.size'] = item.get('text_size', 10)
    r, g, b = item.get('text_color', [0, 0, 0])[:3]
    shape['text.color'] = f'#{r:02X}{g:02X}{b:02X}'

    path = []
    for handle in item.get('handles', []):
        path.append({
            'point': [handle[0], -handle[1]],
            'tangent_in': None,
            'tangent_out': None})
    if item.get('rotation'):
        path = rotate_path(path, item.get('rotation'), get_path_center(path))

    shape['shape.path'] = path

    if item.get('action_mode'):
        shape['action.commands'] = [get_command(item.get('action_script', ''))]

    if item.get('menus'):
        menu = []
        for caption, script in item.get('menus'):
            menu.append(get_menu_command(caption, script))
        shape['action.menu_commands'] = menu

    known_keys = (
        "color",
        "position",
        "rotation",
        "handles",
        "controls",
        "menus",
        "text",
        "action_mode",
        "action_script",
        "text_size",
        "text_color",)

    for key in item.keys():
        if key not in known_keys:
            print(f'WARNING: Unconvertible key {key} found')
            print(item[key])
    return shape


PRE_COMMAND = """ \
# Lines added by dwpicker conversion for compatibility legacy with MGear
# picker script system.
from maya import cmds
import dwpicker

__INIT__ = False
__NAMESPACE__ = dwpicker.current_namespace()
__CONTROLS__ = __targets__

sets = cmds.ls(__CONTROLS__, type='objectSet')
__FLATCONTROLS__ = list(
    {n for n in __CONTROLS__ if cmds.nodeType(n) != 'objectSet'})
if sets:
    __FLATCONTROLS__ = cmds.sets(sets, query=True)

# Here start the original script MGear picker script
#      / \  Usage of __SELF__ variable is not supported by script conversion.
#     / ! \\
#    /_____\\

##############################################################################

"""


def lighter(hexcolor, percent):
    percent = max(0, min(percent, 100))
    color = hexcolor.lstrip('#')
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    r = int(r + (255 - r) * (percent / 100))
    g = int(g + (255 - g) * (percent / 100))
    b = int(b + (255 - b) * (percent / 100))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def get_menu_command(caption, script):
    command = MENU_COMMAND.copy()
    command['caption'] = caption
    command['command'] = f'{PRE_COMMAND}{script}'
    return command


def get_command(script):
    command = COMMAND.copy()
    command['command'] = f'{PRE_COMMAND}{script}'
    return command


def unique_filename(directory, filename, extension):
    filepath = os.path.join(directory, filename) + '.' + extension
    i = 0
    while os.path.exists(filepath):
        filepath = '{base}.{index}.{extension}'.format(
            base=os.path.join(directory, filename),
            index=str(i).zfill(3),
            extension=extension)
        i += 1
    return filepath